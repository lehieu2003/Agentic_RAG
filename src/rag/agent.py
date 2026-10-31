"""Agentic RAG Engine with Query Expansion, Multi-Query Retrieval, and Self-Correction."""

import re
import unicodedata
from typing import Any, Dict, List, Optional
from src.models import Citation, DocumentChunk, QAResponse, RetrievalResult
from src.rag.generator import RAGGenerator
from src.rag.prompt import ABSTAIN_PHRASE
from src.retrieval.base import BaseRetriever


class AgenticRAG:
    """Autonomous RAG agent with query expansion, multi-query retrieval, self-reflection, and corrective re-querying."""

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

    def answer(self, question: str, top_k: int = 5) -> QAResponse:
        """Execute agentic loop: query expansion, multi-query retrieval, self-reflection, and grounded generation."""
        # 0. Chit-chat / Greeting Router: instantaneous response without DB query or abstention warning
        chitchat_reply = self._detect_chitchat(question)
        if chitchat_reply:
            return QAResponse(
                answer=chitchat_reply,
                citations=[],
                abstained=False,
                retrieved_chunks=[],
                rewritten_queries=[question],
                reasoning_steps=["Nhận diện câu hỏi là lời chào hỏi / giao tiếp thông thường (Chit-chat Router)"]
            )

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
        while max_score < self.min_relevance_score and retries < self.max_retries:
            steps.append(
                f"Điểm phù hợp cao nhất ({max_score:.2f}) thấp hơn ngưỡng ({self.min_relevance_score:.2f}). "
                f"Kích hoạt viết lại truy vấn (Query Rewrite vòng {retries + 1})."
            )
            rewritten = self.rewrite_query(question, attempted_queries=all_queries)
            all_queries.append(rewritten)
            steps.append(f"Truy vấn viết lại: '{rewritten}'")

            additional_chunks = self.multi_query_retrieve([rewritten], top_k=top_k)
            steps.append(f"Truy xuất bổ sung được {len(additional_chunks)} đoạn tài liệu từ truy vấn viết lại")

            candidate_chunks = self._merge_chunks(candidate_chunks + additional_chunks, top_k=top_k)
            max_score = max((c.score for c in candidate_chunks), default=0.0)
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
