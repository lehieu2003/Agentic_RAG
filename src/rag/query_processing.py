"""Query expansion, rewriting, deduplication, and multi-query retrieval helpers."""

import re
from typing import Any, Dict, List, Optional

from src.models import DocumentChunk, RetrievalResult
from src.rag.agent_base import AgentBaseMixin


class QueryProcessingMixin(AgentBaseMixin):
    """Builds and merges retrieval queries, including the self-correction rewrite."""

    def expand_query(self, question: str) -> List[str]:
        """Generate search query variations for technical document retrieval."""
        clean_q = question.strip()
        if not clean_q:
            return []

        unaccented_q = self._remove_accents(clean_q)
        variations: List[str] = [clean_q]
        seen = {clean_q.lower()}

        if self.llm_client is not None:
            prompt = (
                f"Cho câu hỏi tra cứu kỹ thuật: '{clean_q}'.\n"
                f"Hãy tạo ra 2 đến 4 biến thể tìm kiếm ngắn gọn nhằm truy xuất tài liệu chính xác nhất:\n"
                f"1. Phân rã nhiệm vụ: Nếu câu hỏi gồm nhiều yêu cầu/tiểu mục con, tạo các truy vấn tìm kiếm riêng biệt cho từng yêu cầu.\n"
                f"2. Khái quát hóa công thức: Nếu câu hỏi chứa số liệu tính toán hoặc bài toán cụ thể, hãy tạo truy vấn tìm công thức/nguyên lý/tiêu chuẩn gốc (loại bỏ các con số cụ thể).\n"
                f"3. Thuật ngữ quốc tế/tiêu chuẩn: Cung cấp thuật ngữ tiếng Anh chuyên ngành hoặc tên tiêu chuẩn kỹ thuật liên quan (ví dụ ISO, IEC, TCVN).\n"
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
                    if len(variations) >= 4:
                        break

        # Always add unaccented variation for OCR and diacritic-insensitive tolerance
        if unaccented_q.lower() not in seen:
            seen.add(unaccented_q.lower())
            variations.append(unaccented_q)

        # Fallback query decomposition when LLM is unavailable (offline / mock mode)
        if len(variations) < 3:
            list_items = [
                re.sub(r"^[\s*•\-\d\.]+", "", line).strip()
                for line in clean_q.splitlines()
                if line.strip().startswith(("-", "•", "*", "1.", "2.", "3.", "4.", "5."))
            ]
            for item in list_items:
                if item and len(item) > 10 and item.lower() not in seen:
                    seen.add(item.lower())
                    variations.append(item)
                    if len(variations) >= 4:
                        break

        # Fallback abstract formula query when equations/numbers are present
        if len(variations) < 3 and bool(re.search(r"=\s*[-+−–]?\d", clean_q)):
            stripped = re.sub(r"[\wα-ωΑ-Ω₁-₉]+\s*=\s*[-+−–]?\d+([.,]\d+)?(\s*[^\s,;()]+)?", "", clean_q)
            stripped = re.sub(r"[-+−–]?\d+([.,]\d+)?(\s*[\w%⁻¹²³/−]+)?", "", stripped)
            stripped = re.sub(r"\s+", " ", stripped).strip(" :,-=.")
            if stripped and len(stripped) > 3 and stripped.lower() not in seen:
                seen.add(stripped.lower())
                variations.append(stripped)

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
        limit = max(top_k * 4, self.candidate_pool_size)
        return sorted_results[:limit]

    def multi_query_retrieve(self, queries: List[str], top_k: int = 5) -> List[RetrievalResult]:
        """Execute retrieval across multiple queries, preserving diversity and deduplicating chunks."""
        if self.retriever is None:
            return []

        guaranteed_diverse: Dict[Any, RetrievalResult] = {}
        all_collected: List[RetrievalResult] = []
        fetch_k = max(top_k * 4, self.candidate_pool_size)

        for q in queries:
            if not q or not q.strip():
                continue
            results = []
            if hasattr(self.retriever, "search") and callable(self.retriever.search):
                res = self.retriever.search(q, top_k=fetch_k)
                if isinstance(res, list):
                    results = res
            if not results and hasattr(self.retriever, "retrieve") and callable(self.retriever.retrieve):
                res = self.retriever.retrieve(q, top_k=fetch_k)
                if isinstance(res, list):
                    results = res
            if not results and hasattr(self.retriever, "hybrid_search") and callable(self.retriever.hybrid_search):
                res = self.retriever.hybrid_search(q, top_k=fetch_k)
                if isinstance(res, list):
                    results = res

            for r in results[:top_k]:
                key = self._get_chunk_key(r.chunk)
                if key not in guaranteed_diverse or r.score > guaranteed_diverse[key].score:
                    guaranteed_diverse[key] = r

            all_collected.extend(results)

        combined = list(guaranteed_diverse.values()) + all_collected
        return self._merge_chunks(combined, top_k=top_k)

    def rewrite_query(
        self,
        question: str,
        attempted_queries: Optional[List[str]] = None,
        missing_aspect: str = ""
    ) -> List[str]:
        """Rewrite question using feedback on missing aspects or broader technical terminology."""
        clean_q = question.strip()
        attempted = attempted_queries or [clean_q]
        variations: List[str] = []

        if self.llm_client is not None:
            prompt = (
                f"Câu hỏi kỹ thuật ban đầu: '{clean_q}'.\n"
                f"Các truy vấn đã thử: {attempted}.\n"
            )
            if missing_aspect:
                prompt += f"Khía cạnh còn thiếu hoặc cần bổ sung thông tin: '{missing_aspect}'.\n"
            prompt += (
                f"Hãy viết lại 2 truy vấn tìm kiếm mới tập trung vào khía cạnh còn thiếu hoặc sử dụng thuật ngữ kỹ thuật chính xác hơn.\n"
                f"Mỗi truy vấn trên một dòng mới. Không thêm số thứ tự, gạch đầu dòng, hay giải thích."
            )
            text = self._call_llm(prompt).strip()
            if text:
                lines = [
                    re.sub(r"^[\s*•\-\d\.]+", "", line).strip()
                    for line in text.splitlines()
                ]
                for line in lines:
                    if line and line.lower() not in [q.lower() for q in attempted]:
                        variations.append(line)
                        if len(variations) >= 2:
                            break

        if not variations:
            if missing_aspect:
                variations.append(f"{clean_q} {missing_aspect}".strip())
            variations.append(f"{clean_q} tổng quan nguyên lý hoạt động")

        return variations
