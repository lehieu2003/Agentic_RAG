"""LLM Answer Generator with citation extraction and abstention enforcement."""

import os
import re
from typing import Any, List, Optional
from src.models import Citation, QAResponse, RetrievalResult
from src.rag.prompt import ABSTAIN_PHRASE, build_rag_prompt


class RAGGenerator:
    """Coordinates LLM calls, parses citations, and applies hallucination guardrails."""

    CITATION_PATTERN = re.compile(
        r"\[Tài liệu:\s*([^,\]|]+?)(?:\s*\|\s*|\s*,\s*)Trang(?:\s*:)?\s*(\d+)\]",
        re.IGNORECASE
    )

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        provider: str = "gemini",
        model_name: Optional[str] = None,
        min_relevance_score: float = 0.50
    ):
        self.llm_client = llm_client
        self.provider = provider
        self.model_name = model_name or ("gemini-2.5-flash" if provider == "gemini" else "gpt-4o-mini")
        self.min_relevance_score = min_relevance_score

    def parse_llm_output(
        self,
        raw_output: str,
        retrieved_chunks: List[RetrievalResult]
    ) -> QAResponse:
        """Parse raw LLM output into structured QAResponse, extracting citations and abstention status."""
        raw_clean = raw_output.strip()

        # Check for abstention
        if ABSTAIN_PHRASE.lower() in raw_clean.lower():
            return QAResponse(
                answer=ABSTAIN_PHRASE,
                citations=[],
                abstained=True,
                retrieved_chunks=retrieved_chunks
            )

        # Extract citations: [Tài liệu: doc.pdf, Trang 12]
        matches = self.CITATION_PATTERN.findall(raw_clean)
        seen_citations = set()
        citations: List[Citation] = []

        for doc_name, page_str in matches:
            doc_name_clean = doc_name.strip()
            page_num = int(page_str.strip())
            key = (doc_name_clean, page_num)
            if key not in seen_citations:
                seen_citations.add(key)
                citations.append(Citation(doc_name=doc_name_clean, page_number=page_num))

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
                raw_text = ABSTAIN_PHRASE
        except Exception as e:
            raw_text = f"{ABSTAIN_PHRASE} (Lỗi kết nối LLM: {str(e)})"

        return self.parse_llm_output(raw_text, relevant_chunks)
