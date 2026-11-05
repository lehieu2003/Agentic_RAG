"""Graph nodes 5-6: context sufficiency grading and feedback-guided query rewrite."""

import json
import re
from typing import Any, Dict

from src.rag.state import AgentState


class GradingNodesMixin:
    """Nodes that decide whether the context is sufficient and retry retrieval."""

    def _node_grade_relevance(self, state: AgentState) -> Dict[str, Any]:
        """Node 5: Context Sufficiency Grader evaluating if reranked chunks contain facts to answer."""
        clean_q = state.get("clean_question", state["question"])
        reranked = state.get("reranked_chunks", [])
        steps = list(state.get("reasoning_steps", []))

        if not reranked:
            steps.append("5. grade_relevance: Không tìm thấy tài liệu phù hợp (ngữ cảnh rỗng)")
            return {
                "is_sufficient": False,
                "grader_feedback": "Không tìm thấy đoạn trích tài liệu nào liên quan.",
                "reasoning_steps": steps
            }

        if self.llm_client is not None:
            context_text = "\n\n".join(
                f"[{idx+1}] Tài liệu: {r.chunk.doc_name}, Trang {r.chunk.page_number}:\n{r.chunk.text}"
                for idx, r in enumerate(reranked)
            )
            prompt = (
                f"Bạn là chuyên gia đánh giá ngữ cảnh tài liệu cho hệ thống RAG kỹ thuật (Context Sufficiency Grader).\n"
                f"Câu hỏi của người dùng: '{clean_q}'\n\n"
                f"Các đoạn trích dẫn tài liệu tìm được:\n{context_text}\n\n"
                f"Nhiệm vụ: Hãy phân tích xem các đoạn trích trên có chứa thông tin hoặc căn cứ thực tế để trả lời cho câu hỏi hay không "
                f"(bao gồm định nghĩa cốt lõi, khái niệm, phạm vi áp dụng, nguyên lý, thông số, công thức hoặc hướng dẫn trong tài liệu, "
                f"kể cả khi các đoạn trích quét từ tài liệu OCR bị thiếu dấu tiếng Việt. "
                f"Đối với câu hỏi tính toán: chỉ cần đoạn trích chứa công thức, định nghĩa hoặc mối quan hệ giữa các đại lượng là đủ căn cứ để tính toán (is_sufficient: true), "
                f"không yêu cầu tài liệu phải có sẵn con số kết quả cụ thể). "
                f"Nếu có căn cứ để trả lời câu hỏi, hãy đánh giá is_sufficient: true. "
                f"Chỉ trả về is_sufficient: false khi các đoạn trích hoàn toàn không chứa thông tin hoặc lệch chủ đề so với câu hỏi.\n"
                f"Trả về kết quả dưới dạng JSON duy nhất với cấu trúc:\n"
                f'{{"is_sufficient": true/false, "missing_aspects": "Mô tả ngắn gọn khía cạnh còn thiếu nếu false, hoặc rỗng nếu true"}}\n'
                f"Chỉ trả về JSON, không giải thích thêm."
            )
            raw = self._call_llm(prompt).strip()
            is_sufficient = True
            missing_aspects = ""
            try:
                json_match = re.search(r"\{.*\}", raw, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    is_sufficient = bool(parsed.get("is_sufficient", True))
                    missing_aspects = str(parsed.get("missing_aspects", "") or "")
                else:
                    if '"is_sufficient": false' in raw.lower() or '"is_sufficient":false' in raw.lower():
                        is_sufficient = False
                        missing_aspects = "Thông tin không đủ theo đánh giá LLM"
            except Exception:
                max_score = max((r.score for r in reranked), default=0.0)
                is_sufficient = max_score >= self.min_relevance_score
                if not is_sufficient:
                    missing_aspects = f"Điểm phù hợp thấp ({max_score:.2f} < {self.min_relevance_score:.2f})"

            if is_sufficient:
                steps.append("5. grade_relevance: Ngữ cảnh đủ thông tin để trả lời câu hỏi")
            else:
                steps.append(f"5. grade_relevance: Ngữ cảnh chưa đủ thông tin. Khía cạnh còn thiếu: {missing_aspects}")

            return {
                "is_sufficient": is_sufficient,
                "grader_feedback": missing_aspects,
                "reasoning_steps": steps
            }

        # Fallback when llm_client is None
        max_score = max((r.score for r in reranked), default=0.0)
        is_sufficient = max_score >= self.min_relevance_score
        missing_aspects = "" if is_sufficient else f"Điểm phù hợp thấp ({max_score:.2f} < {self.min_relevance_score:.2f})"
        if is_sufficient:
            steps.append("5. grade_relevance: Ngữ cảnh đủ thông tin để trả lời câu hỏi")
        else:
            steps.append(f"5. grade_relevance: Ngữ cảnh chưa đủ thông tin. Khía cạnh còn thiếu: {missing_aspects}")

        return {
            "is_sufficient": is_sufficient,
            "grader_feedback": missing_aspects,
            "reasoning_steps": steps
        }

    def _route_after_grade(self, state: AgentState) -> str:
        """Route to 7_generate if sufficient, 6_rewrite_query if retries remaining, else 9_abstain."""
        if state.get("is_sufficient"):
            return "7_generate"
        if state.get("retries", 0) < self.max_retries:
            return "6_rewrite_query"
        return "9_abstain"

    def _node_rewrite_query(self, state: AgentState) -> Dict[str, Any]:
        """Node 6: Feedback-guided Query Rewrite."""
        retries = state.get("retries", 0) + 1
        clean_q = state.get("clean_question", state["question"])
        attempted = state.get("all_queries", [clean_q])
        feedback = state.get("grader_feedback", "")

        new_queries = self.rewrite_query(clean_q, attempted_queries=attempted, missing_aspect=feedback)
        all_q = list(attempted)
        for q in new_queries:
            if q not in all_q:
                all_q.append(q)

        steps = list(state.get("reasoning_steps", []))
        steps.append(
            f"6. rewrite_query: Viết lại truy vấn dựa trên phản hồi (vòng {retries}): {new_queries}"
        )
        return {
            "queries": new_queries,
            "all_queries": all_q,
            "retries": retries,
            "reasoning_steps": steps
        }
