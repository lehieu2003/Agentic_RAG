"""LangGraph-powered Agentic RAG Engine with Query Expansion, Multi-Query Retrieval, and Self-Correction."""

import re
import unicodedata
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, START, END

from src.models import Citation, DocumentChunk, QAResponse, RetrievalResult
from src.rag.generator import RAGGenerator
from src.rag.prompt import ABSTAIN_PHRASE
from src.retrieval.base import BaseRetriever


class AgentState(TypedDict, total=False):
    """Execution state passed between nodes in the LangGraph agentic loop."""

    question: str
    top_k: int
    is_chitchat: bool
    chitchat_reply: Optional[str]
    queries: List[str]
    all_queries: List[str]
    candidate_chunks: List[RetrievalResult]
    relevant_chunks: List[RetrievalResult]
    max_score: float
    retries: int
    abstained: bool
    answer: str
    citations: List[Citation]
    reasoning_steps: List[str]


class AgenticRAG:
    """LangGraph-driven Autonomous RAG agent with query expansion, multi-query retrieval, self-reflection, and corrective re-querying."""

    CHITCHAT_PATTERNS = [
        (
            r"^(xin\s+)?chào(\s+bạn|\s+trợ\s+lý|\s+bot)?[\s\.\?!]*$|^(hello|hi|hey|halo|hé\s+lô|alo)[\s\.\?!]*$|^(chào\s+buổi\s+sáng|good\s+morning|good\s+afternoon|good\s+evening)[\s\.\?!]*$",
            (
                "Xin chào! Tôi là Trợ lý Hỏi đáp Tài liệu Kỹ thuật (Document Q&A Assistant).\n\n"
                "Tôi có thể giúp bạn tra cứu, giải đáp thông số, quy trình kỹ thuật và trích dẫn nguồn số trang chính xác từ các tài liệu bạn đã tải lên (PDF, DOCX, TXT, Hình ảnh OCR).\n\n"
                "Bạn cần tìm hiểu hoặc kiểm tra thông tin gì trong tài liệu hôm nay?"
            )
        ),
        (
            r"^(bạn\s+là\s+ai|who\s+are\s+you|bạn\s+có\s+thể\s+làm\s+gì|what\s+can\s+you\s+do|giới\s+thiệu(\s+về\s+bạn|\s+bản\s+thân)?|hướng\s+dẫn(\s+sử\s+dụng)?|help)[\s\.\?!]*$",
            (
                "Tôi là Trợ lý AI Hỏi đáp Kỹ thuật chuyên sâu. Nhiệm vụ của tôi là phân tích các tài liệu bạn tải lên "
                "và trả lời câu hỏi kèm số trang, tên tài liệu chính xác (Citations). "
                "Nếu câu hỏi không có căn cứ trong tài liệu, tôi sẽ từ chối để tránh suy đoán sai lệch."
            )
        ),
        (
            r"^(cảm\s+ơn|cám\s+ơn|thanks?|thank\s+you)(\s+bạn|\s+nhiều|\s+nhé|\s+trợ\s+lý|\s+bot)?[\s\.\?!]*$",
            (
                "Rất vui được hỗ trợ bạn! Nếu bạn có thêm câu hỏi kỹ thuật nào về tài liệu, hãy cứ đặt câu hỏi nhé."
            )
        ),
        (
            r"^(tạm\s+biệt|bye|goodbye|hẹn\s+gặp\s+lại|bai\s+bai)[\s\.\?!]*$",
            (
                "Tạm biệt bạn! Chúc bạn làm việc hiệu quả và hẹn gặp lại khi bạn cần tra cứu tài liệu!"
            )
        ),
    ]

    def __init__(
        self,
        retriever: BaseRetriever,
        llm_client: Optional[Any] = None,
        provider: str = "gemini",
        model_name: Optional[str] = None,
        min_relevance_score: float = 0.35,
        max_retries: int = 1
    ):
        self.retriever = retriever
        self.llm_client = llm_client
        self.provider = provider
        self.model_name = model_name or ("gemini-3.5-flash-lite" if provider == "gemini" else "gpt-4o-mini")
        self.min_relevance_score = min_relevance_score
        self.max_retries = max_retries

        self.generator = RAGGenerator(
            llm_client=llm_client,
            provider=provider,
            model_name=self.model_name,
            min_relevance_score=min_relevance_score
        )

        # Build and compile LangGraph StateGraph
        self.app = self._build_graph()

    def _remove_accents(self, text: str) -> str:
        """Convert accented Vietnamese text to unaccented ASCII equivalent."""
        s = text.replace("đ", "d").replace("Đ", "D")
        nfkd = unicodedata.normalize("NFKD", s)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def _call_llm(self, prompt: str) -> str:
        """Execute LLM generation with automatic model fallback for high availability."""
        if self.llm_client is None:
            return ""
        if self.provider == "gemini":
            candidate_models = [self.model_name]
            for fb in ["gemini-flash-lite-latest", "gemini-3.1-flash-lite"]:
                if fb not in candidate_models:
                    candidate_models.append(fb)
            for m in candidate_models:
                try:
                    response = self.llm_client.models.generate_content(
                        model=m,
                        contents=prompt
                    )
                    text = response.text or ""
                    if text:
                        return text
                except Exception:
                    continue
            return ""
        elif self.provider == "openai":
            try:
                response = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                )
                return response.choices[0].message.content or ""
            except Exception:
                return ""
        return ""

    def _detect_chitchat(self, text: str) -> Optional[str]:
        """Detect if user query is a greeting, introduction, thanks, or chitchat."""
        clean = text.strip().lower()
        clean_unaccented = self._remove_accents(clean)
        for pattern, reply in self.CHITCHAT_PATTERNS:
            if re.match(pattern, clean, re.IGNORECASE) or re.match(pattern, clean_unaccented, re.IGNORECASE):
                return reply
        return None

    def expand_query(self, question: str) -> List[str]:
        """Generate search query variations for technical document retrieval.

        Produces domain synonyms, English technical terms (e.g. ISO/IEC standards),
        and unaccented Vietnamese to robustly match scanned OCR documents.
        """
        clean_q = question.strip()
        if not clean_q:
            return []

        unaccented_q = self._remove_accents(clean_q)
        variations: List[str] = [clean_q]
        seen = {clean_q.lower()}

        if self.llm_client is not None:
            prompt = (
                f"Cho câu hỏi tra cứu kỹ thuật: '{clean_q}'.\n"
                f"Hãy tạo ra 3 biến thể tìm kiếm ngắn gọn:\n"
                f"1. Thuật ngữ tiếng Anh chuyên ngành hoặc tên tiêu chuẩn quốc tế (ISO/IEC) tương đương.\n"
                f"2. Cụm từ mở rộng kèm lĩnh vực kỹ thuật/đo lường cụ thể.\n"
                f"3. Từ khóa hoặc từ đồng nghĩa ngắn gọn.\n"
                f"Mỗi biến thể trên một dòng mới. Không thêm số thứ tự, gạch đầu dòng, hay giải thích."
            )
            raw_text = self._call_llm(prompt)
            lines = [
                re.sub(r"^[\s*•\-\d\.]+", "", line).strip()
                for line in raw_text.splitlines()
            ]
            for line in lines:
                if line and line.lower() not in seen:
                    seen.add(line.lower())
                    variations.append(line)
                    if len(variations) >= 3:
                        break

        # Always ensure an unaccented variation is included for Vietnamese queries to support OCR text
        if unaccented_q.lower() not in seen:
            seen.add(unaccented_q.lower())
            variations.append(unaccented_q)

        # Deterministic / mock fallback if needed
        if len(variations) < 3:
            fallback = [
                f"{clean_q} thông số kỹ thuật",
                f"{clean_q} hướng dẫn vận hành",
                f"{clean_q} tiêu chuẩn kỹ thuật"
            ]
            for item in fallback:
                if item.lower() not in seen:
                    seen.add(item.lower())
                    variations.append(item)
                    if len(variations) >= 3:
                        break

        return variations[:4]

    def _get_chunk_key(self, chunk: DocumentChunk) -> tuple:
        """Derive deduplication key for a document chunk."""
        chunk_idx = getattr(chunk, "chunk_index", chunk.metadata.get("chunk_index", None))
        if chunk_idx is not None:
            return (chunk.doc_name.strip().lower(), chunk.page_number, chunk_idx)
        if chunk.chunk_id:
            return (chunk.doc_name.strip().lower(), chunk.page_number, chunk.chunk_id)
        return (chunk.doc_name.strip().lower(), chunk.page_number, chunk.text.strip())

    def _merge_chunks(self, chunks: List[RetrievalResult], top_k: int = 5) -> List[RetrievalResult]:
        """Merge retrieval results, keeping highest score for duplicates and sorting descending."""
        merged: Dict[Any, RetrievalResult] = {}
        for r in chunks:
            key = self._get_chunk_key(r.chunk)
            if key not in merged or r.score > merged[key].score:
                merged[key] = r

        sorted_results = sorted(merged.values(), key=lambda r: r.score, reverse=True)
        limit = max(top_k * 5, 25)
        return sorted_results[:limit]

    def multi_query_retrieve(self, queries: List[str], top_k: int = 5) -> List[RetrievalResult]:
        """Execute retrieval across multiple queries, preserving diversity and deduplicating chunks."""
        guaranteed_diverse: Dict[Any, RetrievalResult] = {}
        all_collected: List[RetrievalResult] = []
        fetch_k = max(top_k * 4, 20)

        for q in queries:
            if not q or not q.strip():
                continue
            if hasattr(self.retriever, "search") and callable(self.retriever.search):
                results = self.retriever.search(q, top_k=fetch_k)
            elif hasattr(self.retriever, "retrieve") and callable(self.retriever.retrieve):
                results = self.retriever.retrieve(q, top_k=fetch_k)
            else:
                results = []

            # Retain top chunks from each query formulation to prevent diverse queries (e.g. English standards)
            # from being crowded out by dense language clusters
            for r in results[:top_k]:
                key = self._get_chunk_key(r.chunk)
                if key not in guaranteed_diverse or r.score > guaranteed_diverse[key].score:
                    guaranteed_diverse[key] = r

            all_collected.extend(results)

        # Merge diverse set with general collected results
        combined = list(guaranteed_diverse.values()) + all_collected
        return self._merge_chunks(combined, top_k=top_k)

    def rewrite_query(self, question: str, attempted_queries: List[str]) -> str:
        """Rewrite question using broader technical terminology or synonyms."""
        clean_q = question.strip()
        if self.llm_client is not None:
            prompt = (
                f"Câu hỏi kỹ thuật sau đây không tìm thấy kết quả phù hợp: '{clean_q}'.\n"
                f"Các truy vấn đã thử nhưng chưa đạt: {attempted_queries}.\n"
                f"Hãy viết lại 1 câu truy vấn tìm kiếm mới, dùng thuật ngữ tổng quan hơn hoặc từ đồng nghĩa kỹ thuật.\n"
                f"Chỉ trả về duy nhất 1 câu truy vấn mới, không giải thích."
            )
            text = self._call_llm(prompt).strip()
            if text:
                clean_text = re.sub(r"^[\s*•\-\d\.]+", "", text).strip()
                if clean_text:
                    return clean_text

        # Fallback query rewrite
        return f"{clean_q} tổng quan nguyên lý hoạt động"

    def validate_citations(
        self,
        raw_output: str,
        retrieved_chunks: List[RetrievalResult]
    ) -> QAResponse:
        """Validate that citations in raw_output strictly correspond to retrieved chunks."""
        return self.generator.parse_llm_output(raw_output, retrieved_chunks)

    # -------------------------------------------------------------------------
    # LangGraph Nodes & Conditional Edges
    # -------------------------------------------------------------------------

    def _node_router(self, state: AgentState) -> Dict[str, Any]:
        """Node 1: Detect greetings or system introductory queries."""
        reply = self._detect_chitchat(state["question"])
        if reply:
            return {
                "is_chitchat": True,
                "chitchat_reply": reply,
                "answer": reply,
                "abstained": False,
                "citations": [],
                "candidate_chunks": [],
                "all_queries": [state["question"]],
                "reasoning_steps": ["Nhận diện câu hỏi là lời chào hỏi / giao tiếp thông thường (Chit-chat Router)"]
            }
        return {
            "is_chitchat": False,
            "reasoning_steps": [f"Tiếp nhận câu hỏi: '{state['question']}'"]
        }

    def _route_after_router(self, state: AgentState) -> str:
        """Conditional routing: terminate if chitchat, else proceed to query expansion."""
        if state.get("is_chitchat"):
            return END
        return "expand_query"

    def _node_expand_query(self, state: AgentState) -> Dict[str, Any]:
        """Node 2: Expand query into multi-lingual / OCR-tolerant variations."""
        expanded = self.expand_query(state["question"])
        if not expanded:
            expanded = [state["question"]]
        steps = list(state.get("reasoning_steps", []))
        steps.append(f"Mở rộng truy vấn thành {len(expanded)} biến thể: {expanded}")
        return {
            "queries": expanded,
            "all_queries": list(expanded),
            "reasoning_steps": steps
        }

    def _node_retrieve(self, state: AgentState) -> Dict[str, Any]:
        """Node 3: Execute multi-query retrieval and merge results."""
        queries_to_run = state.get("queries", [state["question"]])
        new_chunks = self.multi_query_retrieve(queries_to_run, top_k=state.get("top_k", 5))
        existing = state.get("candidate_chunks", [])
        merged = self._merge_chunks(existing + new_chunks, top_k=state.get("top_k", 5))
        max_score = max((c.score for c in merged), default=0.0)

        steps = list(state.get("reasoning_steps", []))
        steps.append(f"Truy xuất được {len(merged)} đoạn tài liệu ứng viên (điểm cao nhất: {max_score:.2f})")
        return {
            "candidate_chunks": merged,
            "max_score": max_score,
            "reasoning_steps": steps
        }

    def _route_after_retrieve(self, state: AgentState) -> str:
        """Self-Reflection: check relevance threshold against min_relevance_score."""
        max_score = state.get("max_score", 0.0)
        if max_score >= self.min_relevance_score:
            return "generate"
        if state.get("retries", 0) < self.max_retries:
            return "rewrite_query"
        return "abstain"

    def _node_rewrite_query(self, state: AgentState) -> Dict[str, Any]:
        """Node 4: Corrective Query Rewrite when retrieval score is low."""
        retries = state.get("retries", 0) + 1
        rewritten = self.rewrite_query(state["question"], attempted_queries=state.get("all_queries", []))
        all_q = list(state.get("all_queries", [])) + [rewritten]

        steps = list(state.get("reasoning_steps", []))
        steps.append(
            f"Điểm phù hợp cao nhất ({state.get('max_score', 0.0):.2f}) thấp hơn ngưỡng ({self.min_relevance_score:.2f}). "
            f"Kích hoạt viết lại truy vấn (Query Rewrite vòng {retries}): '{rewritten}'"
        )
        return {
            "queries": [rewritten],
            "all_queries": all_q,
            "retries": retries,
            "reasoning_steps": steps
        }

    def _node_generate(self, state: AgentState) -> Dict[str, Any]:
        """Node 5: Synthesize grounded response using verified context chunks."""
        candidates = state.get("candidate_chunks", [])
        relevant = [c for c in candidates if c.score >= self.min_relevance_score]
        steps = list(state.get("reasoning_steps", []))

        if not relevant:
            steps.append(f"Không có đoạn tài liệu nào đạt ngưỡng tin cậy {self.min_relevance_score:.2f}. Từ chối trả lời (Abstain).")
            return {
                "answer": ABSTAIN_PHRASE,
                "citations": [],
                "abstained": True,
                "relevant_chunks": [],
                "reasoning_steps": steps
            }

        steps.append(f"Tổng hợp câu trả lời từ {len(relevant)} đoạn tài liệu phù hợp")
        resp = self.generator.generate_answer(state["question"], relevant)

        if resp.abstained:
            steps.append("Bộ sinh câu trả lời từ chối do trích dẫn không có căn cứ hoặc thiếu dữ liệu")
        else:
            steps.append(f"Hoàn thành câu trả lời với {len(resp.citations)} trích dẫn hợp lệ")

        return {
            "answer": resp.answer,
            "citations": resp.citations,
            "abstained": resp.abstained,
            "relevant_chunks": relevant,
            "reasoning_steps": steps
        }

    def _node_abstain(self, state: AgentState) -> Dict[str, Any]:
        """Node 6: Explicit abstention guardrail to prevent hallucinations."""
        steps = list(state.get("reasoning_steps", []))
        steps.append(f"Không có đoạn tài liệu nào đạt ngưỡng tin cậy {self.min_relevance_score:.2f}. Từ chối trả lời (Abstain).")
        return {
            "answer": ABSTAIN_PHRASE,
            "citations": [],
            "abstained": True,
            "relevant_chunks": [],
            "reasoning_steps": steps
        }

    def _build_graph(self):
        """Construct and compile the LangGraph StateGraph workflow."""
        workflow = StateGraph(AgentState)

        workflow.add_node("router", self._node_router)
        workflow.add_node("expand_query", self._node_expand_query)
        workflow.add_node("retrieve", self._node_retrieve)
        workflow.add_node("rewrite_query", self._node_rewrite_query)
        workflow.add_node("generate", self._node_generate)
        workflow.add_node("abstain", self._node_abstain)

        workflow.add_edge(START, "router")
        workflow.add_conditional_edges(
            "router",
            self._route_after_router,
            {"expand_query": "expand_query", END: END}
        )
        workflow.add_edge("expand_query", "retrieve")
        workflow.add_conditional_edges(
            "retrieve",
            self._route_after_retrieve,
            {
                "generate": "generate",
                "rewrite_query": "rewrite_query",
                "abstain": "abstain"
            }
        )
        workflow.add_edge("rewrite_query", "retrieve")
        workflow.add_edge("generate", END)
        workflow.add_edge("abstain", END)

        return workflow.compile()

    def draw_png(self, output_path: Optional[str] = "docs/langgraph_workflow.png") -> bytes:
        """Export the compiled LangGraph StateGraph as a PNG diagram.

        Uses LangGraph native draw_mermaid_png() with automatic mermaid.ink fallback.
        """
        try:
            png_bytes = self.app.get_graph().draw_mermaid_png()
        except Exception:
            import base64
            import httpx
            mermaid_str = self.app.get_graph().draw_mermaid()
            encoded = base64.urlsafe_b64encode(mermaid_str.encode("utf-8")).decode("ascii")
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

    def answer(self, question: str, top_k: int = 5) -> QAResponse:
        """Execute the LangGraph workflow and return a structured QAResponse."""
        initial_state: AgentState = {
            "question": question,
            "top_k": top_k,
            "is_chitchat": False,
            "chitchat_reply": None,
            "queries": [],
            "all_queries": [],
            "candidate_chunks": [],
            "relevant_chunks": [],
            "max_score": 0.0,
            "retries": 0,
            "abstained": False,
            "answer": "",
            "citations": [],
            "reasoning_steps": [],
        }

        final_state = self.app.invoke(initial_state)

        all_queries = list(final_state.get("all_queries", []))
        if not all_queries:
            all_queries = [question]

        return QAResponse(
            answer=final_state.get("answer", ""),
            citations=final_state.get("citations", []),
            abstained=final_state.get("abstained", False),
            retrieved_chunks=final_state.get("candidate_chunks", []),
            rewritten_queries=all_queries,
            reasoning_steps=final_state.get("reasoning_steps", [])
        )
