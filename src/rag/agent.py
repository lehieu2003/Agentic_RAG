"""LangGraph-powered Agentic RAG Engine.

The engine combines query contextualization, query expansion, hybrid retrieval,
cross-encoder reranking, a context sufficiency grader, and a citation
self-correction loop. The graph nodes and helper logic live in the focused
mixins under ``src/rag/nodes`` and ``src/rag/{chitchat,query_processing,
agent_base}``; this module wires them together.
"""

from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, START, END

from src.config import settings
from src.models import QAResponse
from src.rag.chitchat import ChitchatMixin
from src.rag.generator import RAGGenerator
from src.rag.nodes.answer import AnswerNodesMixin
from src.rag.nodes.grading import GradingNodesMixin
from src.rag.nodes.intake import IntakeNodesMixin
from src.rag.nodes.retrieval import RetrievalNodesMixin
from src.rag.query_processing import QueryProcessingMixin
from src.rag.state import AgentState
from src.retrieval.base import BaseRetriever
from src.retrieval.reranker import CrossEncoderReranker


class AgenticRAG(
    ChitchatMixin,
    QueryProcessingMixin,
    IntakeNodesMixin,
    RetrievalNodesMixin,
    GradingNodesMixin,
    AnswerNodesMixin,
):
    """LangGraph v2 Closed-Loop Agentic RAG engine.

    Combines hybrid search, reranking, a sufficiency grader, and citation
    correction. Public behavior matches the previous monolithic implementation.
    """

    def __init__(
        self,
        retriever: Optional[BaseRetriever] = None,
        reranker: Optional[CrossEncoderReranker] = None,
        llm_client: Optional[Any] = None,
        provider: str = "gemini",
        model_name: Optional[str] = None,
        min_relevance_score: Optional[float] = None,
        max_retries: Optional[int] = None,
        max_gen_retries: Optional[int] = None,
        candidate_pool_size: Optional[int] = None,
        top_preservation_k: Optional[int] = None,
        complex_query_threshold: Optional[int] = None,
        complex_query_top_k: Optional[int] = None,
    ) -> None:
        self.retriever = retriever
        self.reranker = reranker
        self.llm_client = llm_client
        self.provider = provider
        self.model_name = model_name or ("gemini-3.5-flash-lite" if provider == "gemini" else "gpt-4o-mini")
        self.min_relevance_score = min_relevance_score if min_relevance_score is not None else settings.min_relevance_score
        self.max_retries = max_retries if max_retries is not None else settings.max_retries
        self.max_gen_retries = max_gen_retries if max_gen_retries is not None else settings.max_gen_retries
        self.candidate_pool_size = candidate_pool_size if candidate_pool_size is not None else settings.candidate_pool_size
        self.top_preservation_k = top_preservation_k if top_preservation_k is not None else settings.top_preservation_k
        self.complex_query_threshold = complex_query_threshold if complex_query_threshold is not None else settings.complex_query_threshold
        self.complex_query_top_k = complex_query_top_k if complex_query_top_k is not None else settings.complex_query_top_k

        self.generator = RAGGenerator(
            llm_client=llm_client,
            provider=provider,
            model_name=self.model_name,
            min_relevance_score=self.min_relevance_score
        )

        # Build and compile LangGraph StateGraph
        self.app = self._build_graph()

    def _build_graph(self):
        """Construct and compile the 9+1 numbered node LangGraph StateGraph workflow."""
        workflow = StateGraph(AgentState)

        workflow.add_node("0_contextualize_query", self._node_contextualize_query)
        workflow.add_node("1_router", self._node_router)
        workflow.add_node("2_expand_query", self._node_expand_query)
        workflow.add_node("3_hybrid_retrieve", self._node_hybrid_retrieve)
        workflow.add_node("4_rerank", self._node_rerank)
        workflow.add_node("5_grade_relevance", self._node_grade_relevance)
        workflow.add_node("6_rewrite_query", self._node_rewrite_query)
        workflow.add_node("7_generate", self._node_generate)
        workflow.add_node("8_validate_citations", self._node_validate_citations)
        workflow.add_node("9_abstain", self._node_abstain)

        workflow.add_edge(START, "0_contextualize_query")
        workflow.add_edge("0_contextualize_query", "1_router")
        workflow.add_conditional_edges(
            "1_router",
            self._route_after_router,
            {"2_expand_query": "2_expand_query", END: END}
        )
        workflow.add_edge("2_expand_query", "3_hybrid_retrieve")
        workflow.add_edge("3_hybrid_retrieve", "4_rerank")
        workflow.add_edge("4_rerank", "5_grade_relevance")
        workflow.add_conditional_edges(
            "5_grade_relevance",
            self._route_after_grade,
            {
                "7_generate": "7_generate",
                "6_rewrite_query": "6_rewrite_query",
                "9_abstain": "9_abstain"
            }
        )
        workflow.add_edge("6_rewrite_query", "3_hybrid_retrieve")
        workflow.add_edge("7_generate", "8_validate_citations")
        workflow.add_conditional_edges(
            "8_validate_citations",
            self._route_after_validate,
            {
                END: END,
                "7_generate": "7_generate",
                "9_abstain": "9_abstain"
            }
        )
        workflow.add_edge("9_abstain", END)

        return workflow.compile()

    def draw_png(self, output_path: Optional[str] = "docs/langgraph_workflow.png") -> bytes:
        """Export the compiled LangGraph StateGraph as a PNG diagram with model label gemini-3.5-flash-lite."""
        mermaid_syntax = self.app.get_graph().draw_mermaid()
        mermaid_syntax = mermaid_syntax.replace(
            "7_generate(7_generate)",
            '7_generate("7_generate<br/>(gemini-3.5-flash-lite)")'
        )

        try:
            from langchain_core.runnables.graph_mermaid import draw_mermaid_png
            png_bytes = draw_mermaid_png(mermaid_syntax=mermaid_syntax)
        except Exception:
            import base64
            import httpx
            encoded = base64.urlsafe_b64encode(mermaid_syntax.encode("utf-8")).decode("ascii")
            url = f"https://mermaid.ink/img/{encoded}"
            with httpx.Client(timeout=15.0) as client:
                r = client.get(url)
                png_bytes = r.content

        if output_path:
            from pathlib import Path
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(png_bytes)

        return png_bytes

    def answer(
        self,
        question: str,
        top_k: int = 5,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> QAResponse:
        """Execute the LangGraph workflow and return a structured QAResponse."""
        initial_state: AgentState = {
            "question": question,
            "clean_question": question,
            "standalone_question": question,
            "history": history or [],
            "top_k": top_k,
            "is_chitchat": False,
            "chitchat_reply": None,
            "queries": [],
            "all_queries": [],
            "candidate_chunks": [],
            "reranked_chunks": [],
            "is_sufficient": False,
            "grader_feedback": "",
            "retries": 0,
            "gen_retries": 0,
            "citation_feedback": None,
            "answer": "",
            "citations": [],
            "abstained": False,
            "reasoning_steps": [],
        }

        final_state = self.app.invoke(initial_state)

        all_queries = list(final_state.get("all_queries", []))
        if not all_queries:
            all_queries = [final_state.get("standalone_question", question)]

        retrieved = final_state.get("reranked_chunks") or final_state.get("candidate_chunks", [])

        standalone = final_state.get("standalone_question")
        standalone_to_report = (
            standalone.strip()
            if (standalone and standalone.strip() and standalone.strip() != question.strip())
            else None
        )

        return QAResponse(
            answer=final_state.get("answer", ""),
            citations=final_state.get("citations", []),
            abstained=final_state.get("abstained", False),
            retrieved_chunks=retrieved,
            rewritten_queries=all_queries,
            reasoning_steps=final_state.get("reasoning_steps", []),
            standalone_question=standalone_to_report,
        )


__all__ = ["AgenticRAG", "AgentState"]
