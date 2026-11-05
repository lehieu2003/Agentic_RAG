"""Graph nodes 7-9: grounded synthesis, citation validation, and abstention."""

import logging
from typing import Any, Dict, List

from langgraph.graph import END

from src.models import QAResponse, RetrievalResult
from src.rag.prompt import ABSTAIN_PHRASE, build_rag_prompt
from src.rag.state import AgentState

logger = logging.getLogger(__name__)


class AnswerNodesMixin:
    """Nodes that generate the answer and enforce citation grounding."""

    def _node_generate(self, state: AgentState) -> Dict[str, Any]:
        """Node 7: Grounded answer synthesis."""
        clean_q = state.get("clean_question", state.get("standalone_question", state["question"]))
        context_chunks = state.get("reranked_chunks") or state.get("candidate_chunks", [])
        citation_feedback = state.get("citation_feedback")
        history = state.get("history")
        steps = list(state.get("reasoning_steps", []))

        steps.append(f"7. generate: Tổng hợp câu trả lời từ {len(context_chunks)} đoạn tài liệu phù hợp")

        effective_question = clean_q
        if citation_feedback:
            directive = (
                f"Lưu ý từ lần sinh trước: Bạn đã trích dẫn nguồn không hợp lệ hoặc thiếu số trang: {citation_feedback}. "
                f"Hãy chỉ sử dụng thông tin và số trang có trong các đoạn trích dẫn được cung cấp."
            )
            effective_question = f"[{directive}]\n\n{clean_q}"
            steps.append(f"7. generate: Áp dụng chỉ thị điều chỉnh trích dẫn: {citation_feedback}")

        if self.llm_client is not None:
            prompt = build_rag_prompt(effective_question, context_chunks, history=history)
            try:
                raw_output = self._call_llm(prompt)
            except Exception as e:
                logger.warning(f"LLM generation failed: {e}")
                raw_output = ABSTAIN_PHRASE
            if not raw_output:
                raw_output = ABSTAIN_PHRASE
        else:
            if context_chunks:
                first = context_chunks[0].chunk
                raw_output = f"Theo tài liệu kỹ thuật, {first.text} [Tài liệu: {first.doc_name}, Trang {first.page_number}]."
            else:
                raw_output = ABSTAIN_PHRASE

        return {
            "raw_generation": raw_output,
            "answer": raw_output,
            "reasoning_steps": steps
        }

    def _node_validate_citations(self, state: AgentState) -> Dict[str, Any]:
        """Node 8: Citation Grounding & Format Verification with Self-Correction Loop."""
        raw_output = state.get("raw_generation", state.get("answer", ""))
        context_chunks = state.get("reranked_chunks") or state.get("candidate_chunks", [])
        steps = list(state.get("reasoning_steps", []))
        current_gen_retries = state.get("gen_retries", 0)

        qa_resp = self.validate_citations(raw_output, context_chunks)

        if not qa_resp.abstained:
            steps.append(f"8. validate_citations: Hoàn thành kiểm tra trích dẫn ({len(qa_resp.citations)} trích dẫn hợp lệ)")
            return {
                "is_citation_valid": True,
                "retry_generation": False,
                "answer": qa_resp.answer,
                "citations": qa_resp.citations,
                "abstained": False,
                "reasoning_steps": steps
            }

        # Citation validation failed
        if current_gen_retries < self.max_gen_retries:
            matches = self.generator.CITATION_PATTERN.findall(raw_output)
            if matches:
                invalid_sources = [f"{d} trang {p}" for d, p in matches]
                feedback = f"Trích dẫn không hợp lệ hoặc không có trong tài liệu: {', '.join(invalid_sources)}"
            else:
                feedback = "Thiếu trích dẫn nguồn theo định dạng [Tài liệu: ..., Trang ...]"

            new_gen_retries = current_gen_retries + 1
            steps.append(
                f"8. validate_citations: Phát hiện lỗi trích dẫn ({feedback}). "
                f"Kích hoạt tự sửa chữa (vòng {new_gen_retries})."
            )
            return {
                "is_citation_valid": False,
                "retry_generation": True,
                "citation_feedback": feedback,
                "gen_retries": new_gen_retries,
                "reasoning_steps": steps
            }
        else:
            steps.append(
                f"8. validate_citations: Đã hết lượt thử sửa lỗi trích dẫn "
                f"({current_gen_retries}/{self.max_gen_retries}). Chuyển sang từ chối trả lời."
            )
            return {
                "is_citation_valid": False,
                "retry_generation": False,
                "reasoning_steps": steps
            }

    def _route_after_validate(self, state: AgentState) -> str:
        """Route to END if valid, 7_generate if retry available, else 9_abstain."""
        if state.get("is_citation_valid"):
            return END
        if state.get("retry_generation"):
            return "7_generate"
        return "9_abstain"

    def _node_abstain(self, state: AgentState) -> Dict[str, Any]:
        """Node 9: Explicit abstention guardrail to prevent hallucinations."""
        steps = list(state.get("reasoning_steps", []))
        reason = state.get("grader_feedback") or "Không có đủ thông tin hoặc trích dẫn hợp lệ"
        steps.append(f"9. abstain: Từ chối trả lời (Abstain). Lý do: {reason}")
        return {
            "answer": ABSTAIN_PHRASE,
            "citations": [],
            "abstained": True,
            "reasoning_steps": steps
        }

    def validate_citations(
        self,
        raw_output: str,
        retrieved_chunks: List[RetrievalResult]
    ) -> QAResponse:
        """Validate that citations in raw_output strictly correspond to retrieved chunks."""
        return self.generator.parse_llm_output(raw_output, retrieved_chunks)
