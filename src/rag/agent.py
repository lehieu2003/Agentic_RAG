"""Agentic RAG Engine with Query Expansion, Multi-Query Retrieval, and Self-Correction."""

import re
from typing import Any, Dict, List, Optional
from src.models import Citation, DocumentChunk, QAResponse, RetrievalResult
from src.rag.generator import RAGGenerator
from src.rag.prompt import ABSTAIN_PHRASE
from src.retrieval.base import BaseRetriever


class AgenticRAG:
    """Autonomous RAG agent with query expansion, multi-query retrieval, self-reflection, and corrective re-querying."""

    def __init__(
        self,
        retriever: BaseRetriever,
        llm_client: Optional[Any] = None,
        provider: str = "gemini",
        model_name: Optional[str] = None,
        min_relevance_score: float = 0.45,
        max_retries: int = 1
    ):
        self.retriever = retriever
        self.llm_client = llm_client
        self.provider = provider
        self.model_name = model_name or ("gemini-3.8-flash" if provider == "gemini" else "gpt-4o-mini")
        self.min_relevance_score = min_relevance_score
        self.max_retries = max_retries

        self.generator = RAGGenerator(
            llm_client=llm_client,
            provider=provider,
            model_name=self.model_name,
            min_relevance_score=min_relevance_score
        )

    def expand_query(self, question: str) -> List[str]:
        """Generate 1-3 search query variations for the given technical question.

        Uses LLM if available, otherwise generates deterministic domain variations.
        """
        clean_q = question.strip()
        if not clean_q:
            return []

        if self.llm_client is not None:
            prompt = (
                f"Bạn là trợ lý tìm kiếm tài liệu kỹ thuật.\n"
                f"Cho câu hỏi: '{clean_q}'.\n"
                f"Hãy tạo ra từ 1 đến 3 biến thể tìm kiếm ngắn gọn (từ khóa hoặc câu ngắn) "
                f"để tra cứu tài liệu kỹ thuật hiệu quả nhất.\n"
                f"Mỗi biến thể trên một dòng mới. Không thêm số thứ tự, gạch đầu dòng, hay giải thích."
            )
            try:
                if self.provider == "gemini":
                    response = self.llm_client.models.generate_content(
                        model=self.model_name,
                        contents=prompt
                    )
                    raw_text = response.text or ""
                elif self.provider == "openai":
                    response = self.llm_client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0
                    )
                    raw_text = response.choices[0].message.content or ""
                else:
                    raw_text = ""

                lines = [
                    re.sub(r"^[\s*•\-\d\.]+", "", line).strip()
                    for line in raw_text.splitlines()
                ]
                candidates = [line for line in lines if line]
                if candidates:
                    seen = set()
                    unique_variations = []
                    for c in candidates:
                        if c.lower() not in seen:
                            seen.add(c.lower())
                            unique_variations.append(c)
                            if len(unique_variations) >= 3:
                                break
                    if unique_variations:
                        return unique_variations
            except Exception:
                pass

        # Deterministic / mock fallback
        fallback = [
            clean_q,
            f"{clean_q} thông số kỹ thuật",
            f"{clean_q} hướng dẫn vận hành"
        ]
        seen = set()
        unique_variations = []
        for item in fallback:
            if item.lower() not in seen:
                seen.add(item.lower())
                unique_variations.append(item)
                if len(unique_variations) >= 3:
                    break
        return unique_variations

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
        limit = max(top_k * 2, 10)
        return sorted_results[:limit]

    def multi_query_retrieve(self, queries: List[str], top_k: int = 5) -> List[RetrievalResult]:
        """Execute retrieval across multiple queries, deduplicating chunks and keeping max score."""
        collected: List[RetrievalResult] = []
        for q in queries:
            if not q or not q.strip():
                continue
            if hasattr(self.retriever, "search") and callable(self.retriever.search):
                results = self.retriever.search(q, top_k=top_k)
            elif hasattr(self.retriever, "retrieve") and callable(self.retriever.retrieve):
                results = self.retriever.retrieve(q, top_k=top_k)
            else:
                results = []
            collected.extend(results)

        return self._merge_chunks(collected, top_k=top_k)

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
            try:
                if self.provider == "gemini":
                    response = self.llm_client.models.generate_content(
                        model=self.model_name,
                        contents=prompt
                    )
                    text = (response.text or "").strip()
                elif self.provider == "openai":
                    response = self.llm_client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0
                    )
                    text = (response.choices[0].message.content or "").strip()
                else:
                    text = ""
                if text:
                    clean_text = re.sub(r"^[\s*•\-\d\.]+", "", text).strip()
                    if clean_text:
                        return clean_text
            except Exception:
                pass

        # Fallback query rewrite
        return f"{clean_q} tổng quan nguyên lý hoạt động"

    def validate_citations(
        self,
        raw_output: str,
        retrieved_chunks: List[RetrievalResult]
    ) -> QAResponse:
        """Validate that citations in raw_output strictly correspond to retrieved chunks."""
        return self.generator.parse_llm_output(raw_output, retrieved_chunks)

    def answer(self, question: str, top_k: int = 5) -> QAResponse:
        """Execute agentic loop: query expansion, multi-query retrieval, self-reflection, and grounded generation."""
        steps: List[str] = []
        all_queries: List[str] = []

        steps.append(f"Tiếp nhận câu hỏi: '{question}'")

        # 1. Expand query into variations
        expanded = self.expand_query(question)
        if not expanded:
            expanded = [question]
        all_queries.extend(expanded)
        steps.append(f"Mở rộng truy vấn thành {len(expanded)} biến thể: {expanded}")

        # 2. Multi-query retrieval
        candidate_chunks = self.multi_query_retrieve(expanded, top_k=top_k)
        steps.append(f"Truy xuất được {len(candidate_chunks)} đoạn tài liệu ứng viên từ các truy vấn ban đầu")

        # 3. Self-reflection & Corrective Re-querying
        max_score = max((c.score for c in candidate_chunks), default=0.0)
        retries = 0
        if max_score < self.min_relevance_score and retries < self.max_retries:
            steps.append(
                f"Điểm phù hợp cao nhất ({max_score:.2f}) thấp hơn ngưỡng ({self.min_relevance_score:.2f}). "
                f"Kích hoạt viết lại truy vấn (Query Rewrite)."
            )
            rewritten = self.rewrite_query(question, attempted_queries=all_queries)
            all_queries.append(rewritten)
            steps.append(f"Truy vấn viết lại: '{rewritten}'")

            additional_chunks = self.multi_query_retrieve([rewritten], top_k=top_k)
            steps.append(f"Truy xuất bổ sung được {len(additional_chunks)} đoạn tài liệu từ truy vấn viết lại")

            candidate_chunks = self._merge_chunks(candidate_chunks + additional_chunks, top_k=top_k)
            retries += 1

        # 4. Check if any chunks pass relevance threshold
        relevant_chunks = [c for c in candidate_chunks if c.score >= self.min_relevance_score]
        if not relevant_chunks:
            steps.append(f"Không có đoạn tài liệu nào đạt ngưỡng tin cậy {self.min_relevance_score:.2f}. Từ chối trả lời (Abstain).")
            return QAResponse(
                answer=ABSTAIN_PHRASE,
                citations=[],
                abstained=True,
                retrieved_chunks=candidate_chunks,
                rewritten_queries=all_queries,
                reasoning_steps=steps
            )

        # 5. Synthesize grounded answer
        steps.append(f"Tổng hợp câu trả lời từ {len(relevant_chunks)} đoạn tài liệu phù hợp")
        response = self.generator.generate_answer(question, relevant_chunks)

        if response.abstained:
            steps.append("Bộ sinh câu trả lời từ chối do trích dẫn không có căn cứ hoặc thiếu dữ liệu")
        else:
            steps.append(f"Hoàn thành câu trả lời với {len(response.citations)} trích dẫn hợp lệ")

        response.retrieved_chunks = candidate_chunks
        response.rewritten_queries = all_queries
        response.reasoning_steps = steps
        return response
