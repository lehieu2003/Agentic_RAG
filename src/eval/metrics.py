"""Evaluation metrics for retrieval and response generation."""

from typing import List, Optional
from src.models import RetrievalResult


def calculate_recall_at_k(
    retrieved_chunks: List[RetrievalResult],
    expected_doc: Optional[str],
    expected_pages: List[int],
    k: int
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
    if not expected_doc or not expected_pages or k <= 0:
        return 0.0

    top_k_chunks = retrieved_chunks[:k]
    for result in top_k_chunks:
        chunk = result.chunk
        if chunk.doc_name == expected_doc and chunk.page_number in expected_pages:
            return 1.0

    return 0.0


def evaluate_abstention(should_abstain: bool, actually_abstained: bool) -> bool:
    """Check whether the system correctly abstained or answered as required by ground truth.

    Args:
        should_abstain: Ground truth expectation (True for out-of-scope questions).
        actually_abstained: System response abstained flag.

    Returns:
        True if the system's behavior matched ground truth, False otherwise.
    """
    return should_abstain == actually_abstained

