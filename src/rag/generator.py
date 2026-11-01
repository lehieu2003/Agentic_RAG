"""LLM Answer Generator with citation extraction, citation grounding, and abstention enforcement."""

import os
from pathlib import Path
import re
from typing import Any, List, Optional
import unicodedata
from src.config import settings
from src.models import Citation, QAResponse, RetrievalResult
from src.rag.prompt import ABSTAIN_PHRASE, build_rag_prompt


class RAGGenerator:
    """Coordinates LLM calls, parses citations, and applies hallucination guardrails."""

    CITATION_PATTERN = re.compile(
        r"\[(?:Tài liệu:\s*|Nguồn:\s*)?([^,\]|\(\)\n]+?)(?:\s*\|\s*|\s*,\s*|\s*-\s*|\s*\(|\s+)Trang(?:\s*:)?\s*(\d+)\)?\]",
        re.IGNORECASE
    )
    BRACKET_PATTERN = re.compile(r"\[([^\]\n]+)\]")

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        provider: str = "gemini",
        model_name: Optional[str] = None,
        min_relevance_score: float = 0.35,
        max_page_range: Optional[int] = None
    ):
        self.llm_client = llm_client
        self.provider = provider
        self.model_name = model_name or ("gemini-3.5-flash-lite" if provider == "gemini" else "gpt-4o-mini")
        self.min_relevance_score = min_relevance_score
        self.max_page_range = max_page_range if max_page_range is not None else settings.max_citation_page_range

    def extract_raw_citations(self, text: str) -> List[tuple]:
        """Extract document names and page numbers from text supporting multiple pages and ranges.

        Supports formats:
        - [Tài liệu: doc.pdf, Trang 4]
        - [Tài liệu: doc.pdf, Trang 1, 4]
        - [Tài liệu: doc.pdf, Trang 1 và 4]
        - [doc.pdf, Trang 1-3]
        - [doc.pdf (Trang 5)]
        - [Nguồn: doc.pdf | Trang: 12]
        - [Trang 4] (doc_name empty)
        """
        extracted = []
        for bracket in self.BRACKET_PATTERN.findall(text):
            # Split document name and page part
            parts = re.split(
                r"(?:,\s*|\s*\|\s*|\s*-\s*|\s*\()?(?:các\s+)?(?:trang|page)(?:\s*:)?\s*",
                bracket,
                flags=re.IGNORECASE
            )
            if len(parts) >= 2:
                raw_doc = parts[0].strip()
                raw_doc = re.sub(
                    r"^(?:tài\s+liệu|nguồn|file|tập\s+tin|doc)\s*:\s*",
                    "",
                    raw_doc,
                    flags=re.IGNORECASE
                ).strip()
                raw_pages = parts[1].rstrip(")")
                page_numbers = set()
                # Check for ranges like 1-3 or 1–3
                for r in re.finditer(r"(\d+)\s*[-–—]\s*(\d+)", raw_pages):
                    start, end = int(r.group(1)), int(r.group(2))
                    for p in range(start, min(end + 1, start + self.max_page_range)):
                        page_numbers.add(p)
                # Check for individual numbers
                for num in re.findall(r"\b\d+\b", raw_pages):
                    page_numbers.add(int(num))
                for p in sorted(page_numbers):
                    extracted.append((raw_doc, p))

        # Fallback to standard regex if bracket split didn't find any
        if not extracted:
            for doc_name, page_str in self.CITATION_PATTERN.findall(text):
                try:
                    extracted.append((doc_name.strip(), int(page_str.strip())))
                except ValueError:
                    continue

        return extracted

    def parse_llm_output(
        self,
        raw_output: str,
        retrieved_chunks: List[RetrievalResult]
    ) -> QAResponse:
        """Parse raw LLM output into structured QAResponse, extracting citations and abstention status.

        Enforces grounding: citations must exist in retrieved_chunks, otherwise they are discarded.
        If an answer has no grounded citations, it is flagged as abstained to prevent hallucination.
        """
        raw_clean = raw_output.strip()

        # Check for explicit abstention
        is_explicit_abstain = (
            raw_clean == ABSTAIN_PHRASE
            or raw_clean.rstrip(".").strip() == ABSTAIN_PHRASE.rstrip(".")
            or (not retrieved_chunks and ABSTAIN_PHRASE.lower() in raw_clean.lower())
        )
        if is_explicit_abstain:
            return QAResponse(
                answer=ABSTAIN_PHRASE,
                citations=[],
                abstained=True,
                retrieved_chunks=retrieved_chunks
            )

        def _norm(s: str) -> str:
            return unicodedata.normalize("NFC", s).strip().lower()

        # Build mapping of valid sources: {(normalized_doc_name, page_number): canonical_doc_name}
        valid_sources: dict = {}
        for r in retrieved_chunks:
            norm_name = _norm(r.chunk.doc_name)
            valid_sources[(norm_name, r.chunk.page_number)] = r.chunk.doc_name

        # Extract citations: support multi-page citations and flexible formats
        raw_citations = self.extract_raw_citations(raw_clean)
        seen_citations = set()
        citations: List[Citation] = []

        for doc_name, page_num in raw_citations:
            doc_name_clean = doc_name.strip()
            norm_cited = _norm(doc_name_clean)

            # Check grounding: exact match first, then flexible match (stem or substring)
            matched_canonical_name = None
            if (norm_cited, page_num) in valid_sources:
                matched_canonical_name = valid_sources[(norm_cited, page_num)]
            elif norm_cited:
                for (v_doc, v_page), orig_doc in valid_sources.items():
                    if v_page == page_num:
                        if norm_cited in v_doc or v_doc in norm_cited:
                            matched_canonical_name = orig_doc
                            break
                        if Path(norm_cited).stem == Path(v_doc).stem:
                            matched_canonical_name = orig_doc
                            break
            else:
                # LLM cited without document name (e.g. [Trang 4]), infer from single-doc context
                candidate_docs = [orig_doc for (v_doc, v_page), orig_doc in valid_sources.items() if v_page == page_num]
                if len(candidate_docs) == 1:
                    matched_canonical_name = candidate_docs[0]
                elif len(set(valid_sources.values())) == 1:
                    matched_canonical_name = list(valid_sources.values())[0]

            if matched_canonical_name is not None:
                source_key = (_norm(matched_canonical_name), page_num)
                if source_key not in seen_citations:
                    seen_citations.add(source_key)
                    citations.append(Citation(doc_name=matched_canonical_name, page_number=page_num))

        # Grounding guardrail: If retrieved chunks exist but answer provides zero valid grounded citations
        if retrieved_chunks and not citations:
            return QAResponse(
                answer=ABSTAIN_PHRASE,
                citations=[],
                abstained=True,
                retrieved_chunks=retrieved_chunks
            )

        return QAResponse(
            answer=raw_clean,
            citations=citations,
            abstained=False,
            retrieved_chunks=retrieved_chunks
        )

    def generate_answer(
        self,
        question: str,
        context_chunks: List[RetrievalResult]
    ) -> QAResponse:
        """Generate answer for user question using retrieved chunks as context.

        Args:
            question: User question.
            context_chunks: List of retrieved context chunks.

        Returns:
            QAResponse model.
        """
        # Guardrail 1: Empty chunks or top result below minimum relevance score
        relevant_chunks = [c for c in context_chunks if c.score >= self.min_relevance_score]
        if not relevant_chunks:
            return QAResponse(
                answer=ABSTAIN_PHRASE,
                citations=[],
                abstained=True,
                retrieved_chunks=context_chunks
            )

        prompt = build_rag_prompt(question, relevant_chunks)

        # Mock / Test mode when client is None
        if self.llm_client is None:
            first_chunk = relevant_chunks[0].chunk
            raw_output = f"Theo tài liệu kỹ thuật, {first_chunk.text} [Tài liệu: {first_chunk.doc_name}, Trang {first_chunk.page_number}]."
            return self.parse_llm_output(raw_output, relevant_chunks)

        # Live LLM API invocation
        try:
            if self.provider == "gemini":
                candidate_models = [self.model_name]
                for fb in ["gemini-flash-lite-latest", "gemini-3.1-flash-lite"]:
                    if fb not in candidate_models:
                        candidate_models.append(fb)
                raw_text = ""
                last_err = None
                for m in candidate_models:
                    try:
                        response = self.llm_client.models.generate_content(
                            model=m,
                            contents=prompt
                        )
                        raw_text = response.text or ""
                        if raw_text:
                            break
                    except Exception as err:
                        last_err = err
                        continue
                if not raw_text and last_err:
                    raise last_err
            elif self.provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                )
                raw_text = response.choices[0].message.content or ""
            else:
                raw_text = ABSTAIN_PHRASE
        except Exception as e:
            raw_text = f"{ABSTAIN_PHRASE} (Lỗi kết nối LLM: {str(e)})"

        return self.parse_llm_output(raw_text, relevant_chunks)
