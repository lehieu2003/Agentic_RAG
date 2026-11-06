"""Evaluation metrics for retrieval and grounded answer generation."""

import math
import re
import unicodedata
from collections import Counter
from typing import Any, List, Optional, Sequence

from src.models import RetrievalResult

_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def _normalize_doc_name(name: Any) -> str:
    """Normalize a document name for comparison (NFC + case-insensitive)."""
    if name is None:
        return ""
    return unicodedata.normalize("NFC", str(name)).strip().casefold()


def _normalize_pages(pages: Optional[Sequence[Any]]) -> set:
    """Convert expected page numbers into a set of ints, ignoring invalid values."""
    normalized = set()
    for page in pages or []:
        try:
            normalized.add(int(page))
        except (TypeError, ValueError):
            continue
    return normalized


def _first_relevant_rank(
    retrieved_chunks: List[RetrievalResult],
    expected_doc: Optional[str],
    expected_pages: List[int],
    k: int,
) -> Optional[int]:
    """Return the 1-indexed rank of the first relevant chunk within top-k, else None."""
    if not expected_doc or not expected_pages or k <= 0:
        return None

    target_doc = _normalize_doc_name(expected_doc)
    target_pages = _normalize_pages(expected_pages)

    for rank, result in enumerate(retrieved_chunks[:k], start=1):
        chunk = result.chunk
        if _normalize_doc_name(chunk.doc_name) == target_doc and chunk.page_number in target_pages:
            return rank

    return None


def calculate_recall_at_k(
    retrieved_chunks: List[RetrievalResult],
    expected_doc: Optional[str],
    expected_pages: List[int],
    k: int,
) -> float:
    """Calculate Recall@K (hit rate) for a single query.

    A hit is recorded (1.0) if at least one chunk in the top-K retrieved results
    matches the expected document name and one of the expected page numbers.

    Args:
        retrieved_chunks: Ranked list of RetrievalResults.
        expected_doc: Target document filename (e.g. 'pump_manual.pdf').
        expected_pages: List of target 1-indexed page numbers.
        k: Cutoff rank K.

    Returns:
        1.0 if hit within top-k, 0.0 otherwise.
    """
    return 1.0 if _first_relevant_rank(retrieved_chunks, expected_doc, expected_pages, k) else 0.0


def calculate_mrr_at_k(
    retrieved_chunks: List[RetrievalResult],
    expected_doc: Optional[str],
    expected_pages: List[int],
    k: int,
) -> float:
    """Calculate Reciprocal Rank at K for a single query (0.0 when there is no hit)."""
    rank = _first_relevant_rank(retrieved_chunks, expected_doc, expected_pages, k)
    return 1.0 / rank if rank else 0.0


def calculate_ndcg_at_k(
    retrieved_chunks: List[RetrievalResult],
    expected_doc: Optional[str],
    expected_pages: List[int],
    k: int,
) -> float:
    """Calculate binary-relevance nDCG@K for a single query.

    With one relevant item per query, IDCG is 1.0, so nDCG@K simplifies to
    1 / log2(rank + 1) for the first relevant hit.
    """
    rank = _first_relevant_rank(retrieved_chunks, expected_doc, expected_pages, k)
    return 1.0 / math.log2(rank + 1) if rank else 0.0


def calculate_token_f1(prediction: str, reference: str) -> float:
    """Calculate SQuAD-style token-level F1 between a prediction and a reference answer."""
    prediction_tokens = _TOKEN_PATTERN.findall(unicodedata.normalize("NFC", prediction or "").casefold())
    reference_tokens = _TOKEN_PATTERN.findall(unicodedata.normalize("NFC", reference or "").casefold())

    if not prediction_tokens and not reference_tokens:
        return 1.0
    if not prediction_tokens or not reference_tokens:
        return 0.0

    overlap = sum((Counter(prediction_tokens) & Counter(reference_tokens)).values())
    if overlap == 0:
        return 0.0

    precision = overlap / len(prediction_tokens)
    recall = overlap / len(reference_tokens)
    return 2 * precision * recall / (precision + recall)


def _citation_doc_page(citation: Any) -> tuple:
    """Extract (doc_name, page_number) from a Citation model or plain dict."""
    if isinstance(citation, dict):
        doc_name = citation.get("doc_name") or citation.get("filename")
        page_number = citation.get("page_number") or citation.get("page")
    else:
        doc_name = getattr(citation, "doc_name", None) or getattr(citation, "filename", None)
        page_number = getattr(citation, "page_number", None) or getattr(citation, "page", None)

    try:
        page_number = int(page_number) if page_number is not None else None
    except (TypeError, ValueError):
        page_number = None

    return _normalize_doc_name(doc_name), page_number


def calculate_citation_precision(
    citations: Sequence[Any],
    retrieved_chunks: List[RetrievalResult],
) -> float:
    """Calculate the fraction of cited (document, page) pairs grounded in retrieved chunks.

    Returns 1.0 when the answer contains no citations (vacuously grounded), so that
    correct abstentions are not penalized. Callers should only run this metric for
    non-abstained answers when they need a strict citation-quality signal.
    """
    if not citations:
        return 1.0

    valid_sources = {
        (_normalize_doc_name(result.chunk.doc_name), result.chunk.page_number)
        for result in retrieved_chunks
    }

    grounded = 0
    for citation in citations:
        if _citation_doc_page(citation) in valid_sources:
            grounded += 1

    return grounded / len(citations)


def evaluate_abstention(should_abstain: bool, actually_abstained: bool) -> bool:
    """Check whether the system correctly abstained or answered as required by ground truth.

    Args:
        should_abstain: Ground truth expectation (True for out-of-scope questions).
        actually_abstained: System response abstained flag.

    Returns:
        True if the system's behavior matched ground truth, False otherwise.
    """
    return should_abstain == actually_abstained
