"""LangGraph-powered Agentic RAG Engine with Query Expansion, Hybrid Retrieval, Cross-Encoder Reranking, Grader, and Citation Self-Correction."""

import json
import re
import unicodedata
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, START, END

from src.models import Citation, DocumentChunk, QAResponse, RetrievalResult
from src.rag.generator import RAGGenerator
from src.rag.prompt import ABSTAIN_PHRASE, build_rag_prompt
from src.retrieval.base import BaseRetriever
from src.retrieval.reranker import CrossEncoderReranker


class AgentState(TypedDict, total=False):
    """Execution state passed between nodes in the Agentic RAG v2 graph."""

    # Input queries
    question: str                         # Raw user query
    clean_question: str                   # Cleaned query after removing greeting prefixes
    is_chitchat: bool                     # True if query is purely social/greeting
    chitchat_reply: Optional[str]         # Canned friendly response for greetings

    # Retrieval & Reranking
    queries: List[str]                    # Active queries for this iteration
    all_queries: List[str]                # Cumulative query history
    candidate_chunks: List[RetrievalResult]  # Candidates from RRF (top 20)
    reranked_chunks: List[RetrievalResult]   # Top reranked chunks (top 5)

    # Grading & Reflection
    is_sufficient: bool                   # True if chunks contain sufficient factual answers
    grader_feedback: str                  # Explanation of missing information if insufficient
    retries: int                          # Retrieval rewrite attempt counter (max 1)

    # Generation & Self-Correction
    gen_retries: int                      # Citation correction attempt counter (max 1)
    citation_feedback: Optional[str]      # Error description passed back to generator
    answer: str                           # Synthesized text
    citations: List[Citation]             # Validated citations
    abstained: bool                       # True if refusing to answer

    # Observability
    reasoning_steps: List[str]            # Step-by-step audit log for UI inspection

    # Graph flow auxiliary
    top_k: int
    raw_generation: str
    is_citation_valid: bool
    retry_generation: bool
    relevant_chunks: List[RetrievalResult]
    max_score: float


class AgenticRAG:
    """LangGraph v2 Closed-Loop Agentic RAG engine with hybrid search, reranker, sufficiency grader, and citation correction."""

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

    GREETING_PREFIX_PATTERN = re.compile(
        r"^(?:xin\s+chào|chào\s+(?:bạn|trợ\s+lý|bot|ad|anh|chị|em|mọi\s+người)?|hello|hi|hey|halo|hé\s+lô|alo|good\s+morning|good\s+afternoon|good\s+evening)\s*[,.:;!\-–—]*\s*",
        re.IGNORECASE
    )

    def __init__(
        self,
        retriever: Optional[BaseRetriever] = None,
        reranker: Optional[CrossEncoderReranker] = None,
        llm_client: Optional[Any] = None,
        provider: str = "gemini",
        model_name: Optional[str] = None,
        min_relevance_score: float = 0.35,
        max_retries: int = 1,
        max_gen_retries: int = 1
    ) -> None:
        self.retriever = retriever
        self.reranker = reranker
        self.llm_client = llm_client
        self.provider = provider
        self.model_name = model_name or ("gemini-3.5-flash-lite" if provider == "gemini" else "gpt-4o-mini")
        self.min_relevance_score = min_relevance_score
        self.max_retries = max_retries
        self.max_gen_retries = max_gen_retries

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
        """Generate search query variations for technical document retrieval."""
        clean_q = question.strip()
        if not clean_q:
            return []

        unaccented_q = self._remove_accents(clean_q)
        variations: List[str] = [clean_q]
        seen = {clean_q.lower()}

        # 1. Calculation & formula query abstraction (strip concrete user numbers)
        is_calc_query = any(w in clean_q.lower() for w in [
            "tính", "tinh", "reynolds", "npsh", "cột áp", "cot ap",
            "vận tốc", "van toc", "lưu lượng", "luu luong", "hiệu suất",
            "hieu suat", "công suất", "cong suat", "sai số", "sai so", "dung sai"
        ])
        if is_calc_query:
            stripped = re.sub(r"\b\d+([.,]\d+)?(\s*[a-zA-Z%⁻¹²³/−]+)?\b", "", clean_q)
            stripped = re.sub(r"\s+", " ", stripped).strip(" :,-=")
            if stripped:
                calc_variation = f"công thức {stripped}".strip()
                if calc_variation.lower() not in seen:
                    seen.add(calc_variation.lower())
                    variations.append(calc_variation)

        if self.llm_client is not None:
            prompt = (
                f"Cho câu hỏi tra cứu kỹ thuật: '{clean_q}'.\n"
                f"Hãy tạo ra 3 biến thể tìm kiếm ngắn gọn:\n"
                f"1. Thuật ngữ tiếng Anh chuyên ngành hoặc tên tiêu chuẩn quốc tế (ISO/IEC) tương đương.\n"
                f"2. Cụm từ mở rộng kèm lĩnh vực kỹ thuật/đo lường cụ thể.\n"
                f"3. Từ khóa hoặc tên công thức/nguyên lý tổng quát (nếu câu hỏi có số liệu tính toán, hãy bỏ các con số cụ thể để tìm trúng trang chứa công thức trong tiêu chuẩn).\n"
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

        if unaccented_q.lower() not in seen:
            seen.add(unaccented_q.lower())
            variations.append(unaccented_q)

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
        limit = max(top_k * 4, 20)
        return sorted_results[:limit]

    def multi_query_retrieve(self, queries: List[str], top_k: int = 5) -> List[RetrievalResult]:
        """Execute retrieval across multiple queries, preserving diversity and deduplicating chunks."""
        if self.retriever is None:
            return []

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

    def validate_citations(
        self,
        raw_output: str,
        retrieved_chunks: List[RetrievalResult]
    ) -> QAResponse:
        """Validate that citations in raw_output strictly correspond to retrieved chunks."""
        return self.generator.parse_llm_output(raw_output, retrieved_chunks)

    # -------------------------------------------------------------------------
    # LangGraph Nodes & Conditional Edges (8+1 Numbered Nodes)
    # -------------------------------------------------------------------------

    def _node_router(self, state: AgentState) -> Dict[str, Any]:
        """Node 1: Smart Chit-chat & Intent Extractor."""
        raw_question = state["question"].strip()

        # 1. Pure chitchat check on full query
        reply = self._detect_chitchat(raw_question)
        if reply:
            return {
                "clean_question": raw_question,
                "is_chitchat": True,
                "chitchat_reply": reply,
                "answer": reply,
                "abstained": False,
                "citations": [],
                "candidate_chunks": [],
                "reranked_chunks": [],
                "all_queries": [raw_question],
                "reasoning_steps": ["1. router: Nhận diện câu hỏi là lời chào hỏi / giao tiếp thông thường (Chit-chat Router)"]
            }

        # 2. Greeting prefix stripping for mixed-intent queries
        clean_q = self.GREETING_PREFIX_PATTERN.sub("", raw_question).strip()
        if not clean_q:
            clean_q = raw_question

        reply_stripped = self._detect_chitchat(clean_q)
        if reply_stripped:
            return {
                "clean_question": clean_q,
                "is_chitchat": True,
                "chitchat_reply": reply_stripped,
                "answer": reply_stripped,
                "abstained": False,
                "citations": [],
                "candidate_chunks": [],
                "reranked_chunks": [],
                "all_queries": [clean_q],
                "reasoning_steps": ["1. router: Nhận diện câu hỏi là lời chào hỏi / giao tiếp thông thường (Chit-chat Router)"]
            }

        return {
            "clean_question": clean_q,
            "is_chitchat": False,
            "reasoning_steps": [f"1. router: Đã chuẩn hóa câu hỏi: '{clean_q}' (loại bỏ lời chào hỏi nếu có)"]
        }

    def _route_after_router(self, state: AgentState) -> str:
        """Route to END if pure chitchat, else proceed to 2_expand_query."""
        if state.get("is_chitchat"):
            return END
        return "2_expand_query"

    def _node_expand_query(self, state: AgentState) -> Dict[str, Any]:
        """Node 2: Multilingual / OCR query generator."""
        clean_q = state.get("clean_question", state["question"])
        expanded = self.expand_query(clean_q)
        if not expanded:
            expanded = [clean_q]
        steps = list(state.get("reasoning_steps", []))
        steps.append(f"2. expand_query: Mở rộng truy vấn thành {len(expanded)} biến thể: {expanded}")
        return {
            "queries": expanded,
            "all_queries": list(expanded),
            "reasoning_steps": steps
        }

    def _node_hybrid_retrieve(self, state: AgentState) -> Dict[str, Any]:
        """Node 3: Multi-query retrieval merging candidates via RRF."""
        queries_to_run = state.get("queries") or [state.get("clean_question", state["question"])]
        top_k = state.get("top_k", 5)
        new_chunks = self.multi_query_retrieve(queries_to_run, top_k=top_k)
        existing = state.get("candidate_chunks", [])
        merged = self._merge_chunks(existing + new_chunks, top_k=top_k)
        candidate_pool = merged[:20]
        max_score = max((c.score for c in candidate_pool), default=0.0)

        steps = list(state.get("reasoning_steps", []))
        steps.append(
            f"3. hybrid_retrieve: Truy xuất được {len(candidate_pool)} đoạn tài liệu ứng viên "
            f"từ {len(queries_to_run)} truy vấn (điểm cao nhất: {max_score:.2f})"
        )
        return {
            "candidate_chunks": candidate_pool,
            "max_score": max_score,
            "reasoning_steps": steps
        }

    def _node_rerank(self, state: AgentState) -> Dict[str, Any]:
        """Node 4: Local Cross-Encoder Reranking."""
        clean_q = state.get("clean_question", state["question"])
        candidates = state.get("candidate_chunks", [])
        top_k = state.get("top_k", 5)
        steps = list(state.get("reasoning_steps", []))

        if self.reranker is not None and candidates:
            try:
                reranked = self.reranker.rerank(clean_q, candidates, top_k=top_k)
            except Exception as e:
                steps.append(f"4. rerank: Cảnh báo lỗi reranker ({str(e)}), dùng kết quả truy xuất gốc.")
                reranked = candidates[:top_k]
        else:
            reranked = candidates[:top_k]

        # Guard: Preserve top candidates from hybrid search if absent from reranked set
        reranked_keys = {self._get_chunk_key(r.chunk) for r in reranked}
        for top_candidate in candidates[:2]:
            key = self._get_chunk_key(top_candidate.chunk)
            if key not in reranked_keys:
                reranked.append(top_candidate)
                reranked_keys.add(key)

        steps.append(f"4. rerank: Đã đánh giá và xếp hạng lại {len(reranked)} đoạn tài liệu phù hợp nhất")
        return {
            "reranked_chunks": reranked,
            "reasoning_steps": steps
        }

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

    def _node_generate(self, state: AgentState) -> Dict[str, Any]:
        """Node 7: Grounded answer synthesis."""
        clean_q = state.get("clean_question", state["question"])
        context_chunks = state.get("reranked_chunks") or state.get("candidate_chunks", [])
        citation_feedback = state.get("citation_feedback")
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
            prompt = build_rag_prompt(effective_question, context_chunks)
            raw_output = self._call_llm(prompt)
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

    def _build_graph(self):
        """Construct and compile the 8+1 numbered node LangGraph StateGraph workflow."""
        workflow = StateGraph(AgentState)

        workflow.add_node("1_router", self._node_router)
        workflow.add_node("2_expand_query", self._node_expand_query)
        workflow.add_node("3_hybrid_retrieve", self._node_hybrid_retrieve)
        workflow.add_node("4_rerank", self._node_rerank)
        workflow.add_node("5_grade_relevance", self._node_grade_relevance)
        workflow.add_node("6_rewrite_query", self._node_rewrite_query)
        workflow.add_node("7_generate", self._node_generate)
        workflow.add_node("8_validate_citations", self._node_validate_citations)
        workflow.add_node("9_abstain", self._node_abstain)

        workflow.add_edge(START, "1_router")
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

    def answer(self, question: str, top_k: int = 5) -> QAResponse:
        """Execute the LangGraph workflow and return a structured QAResponse."""
        initial_state: AgentState = {
            "question": question,
            "clean_question": question,
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
            all_queries = [question]

        retrieved = final_state.get("reranked_chunks") or final_state.get("candidate_chunks", [])

        return QAResponse(
            answer=final_state.get("answer", ""),
            citations=final_state.get("citations", []),
            abstained=final_state.get("abstained", False),
            retrieved_chunks=retrieved,
            rewritten_queries=all_queries,
            reasoning_steps=final_state.get("reasoning_steps", [])
        )
