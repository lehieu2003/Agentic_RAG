"""Unit tests for HybridRetriever with Reciprocal Rank Fusion (RRF)."""

from unittest.mock import MagicMock
import pytest

from src.models import DocumentChunk, RetrievalResult
from src.retrieval.base import BaseRetriever
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.hybrid import HybridRetriever


def _create_chunk(chunk_id: str, text: str = "sample text") -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        doc_name="test.pdf",
        page_number=1,
        text=text,
        metadata={},
    )


def test_hybrid_conforms_to_base_retriever():
    """Verify HybridRetriever is a subclass of BaseRetriever."""
    dense_mock = MagicMock(spec=BaseRetriever)
    sparse_mock = MagicMock(spec=BM25Retriever)
    hybrid = HybridRetriever(dense_retriever=dense_mock, sparse_retriever=sparse_mock)

    assert isinstance(hybrid, BaseRetriever)
    assert issubclass(HybridRetriever, BaseRetriever)


def test_rrf_score_calculation_and_deduplication():
    """Verify RRF formula sum(1.0 / (rrf_k + rank)) and chunk deduplication."""
    chunk1 = _create_chunk("chunk-1", "Standard TCVN 9222:2012")
    chunk2 = _create_chunk("chunk-2", "Pump ISO 9906:1999 test")
    chunk3 = _create_chunk("chunk-3", "General safety guideline")

    # Dense returns [chunk1 (rank 1), chunk2 (rank 2)]
    dense_results = [
        RetrievalResult(chunk=chunk1, score=0.95),
        RetrievalResult(chunk=chunk2, score=0.85),
    ]
    # Sparse returns [chunk2 (rank 1), chunk3 (rank 2)]
    sparse_results = [
        RetrievalResult(chunk=chunk2, score=1.0),
        RetrievalResult(chunk=chunk3, score=0.5),
    ]

    dense_mock = MagicMock(spec=BaseRetriever)
    dense_mock.search.return_value = dense_results
    sparse_mock = MagicMock(spec=BM25Retriever)
    sparse_mock.search.return_value = sparse_results

    rrf_k = 60
    hybrid = HybridRetriever(
        dense_retriever=dense_mock,
        sparse_retriever=sparse_mock,
        rrf_k=rrf_k,
    )

    results = hybrid.search("test query", top_k=10)

    # chunk2 is ranked 2 in dense, 1 in sparse
    expected_chunk2_score = (1.0 / (rrf_k + 2)) + (1.0 / (rrf_k + 1))
    # chunk1 is ranked 1 in dense, absent in sparse
    expected_chunk1_score = 1.0 / (rrf_k + 1)
    # chunk3 is absent in dense, ranked 2 in sparse
    expected_chunk3_score = 1.0 / (rrf_k + 2)

    assert len(results) == 3

    # Ranking order: chunk2 (highest sum) > chunk1 > chunk3
    assert results[0].chunk.chunk_id == "chunk-2"
    assert results[0].score == pytest.approx(expected_chunk2_score, rel=1e-5)

    assert results[1].chunk.chunk_id == "chunk-1"
    assert results[1].score == pytest.approx(expected_chunk1_score, rel=1e-5)

    assert results[2].chunk.chunk_id == "chunk-3"
    assert results[2].score == pytest.approx(expected_chunk3_score, rel=1e-5)


def test_top_k_candidate_truncation_and_descending_sorting():
    """Verify results are strictly sorted descending by score and truncated to top_k."""
    dense_chunks = [_create_chunk(f"d-{i}") for i in range(1, 11)]
    sparse_chunks = [_create_chunk(f"s-{i}") for i in range(1, 11)]

    dense_results = [RetrievalResult(chunk=c, score=1.0 / i) for i, c in enumerate(dense_chunks, start=1)]
    sparse_results = [RetrievalResult(chunk=c, score=1.0 / i) for i, c in enumerate(sparse_chunks, start=1)]

    dense_mock = MagicMock(spec=BaseRetriever)
    dense_mock.search.return_value = dense_results
    sparse_mock = MagicMock(spec=BM25Retriever)
    sparse_mock.search.return_value = sparse_results

    hybrid = HybridRetriever(dense_retriever=dense_mock, sparse_retriever=sparse_mock, rrf_k=60)
    top_k = 5
    results = hybrid.search("query", top_k=top_k)

    assert len(results) == top_k
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_delegation_of_index_chunks():
    """Verify index_chunks delegates to both dense and sparse retrievers."""
    chunks = [_create_chunk("c1"), _create_chunk("c2")]

    dense_mock = MagicMock(spec=BaseRetriever)
    dense_mock.index_chunks.return_value = len(chunks)
    sparse_mock = MagicMock(spec=BM25Retriever)
    sparse_mock.index_chunks.return_value = len(chunks)

    hybrid = HybridRetriever(dense_retriever=dense_mock, sparse_retriever=sparse_mock)
    indexed_count = hybrid.index_chunks(chunks)

    dense_mock.index_chunks.assert_called_once_with(chunks)
    sparse_mock.index_chunks.assert_called_once_with(chunks)
    assert indexed_count == len(chunks)


def test_index_chunks_empty_list():
    """Verify index_chunks with empty list returns 0 and does not fail."""
    dense_mock = MagicMock(spec=BaseRetriever)
    sparse_mock = MagicMock(spec=BM25Retriever)

    hybrid = HybridRetriever(dense_retriever=dense_mock, sparse_retriever=sparse_mock)
    indexed_count = hybrid.index_chunks([])

    assert indexed_count == 0
    dense_mock.index_chunks.assert_not_called()
    sparse_mock.index_chunks.assert_not_called()


def test_empty_or_invalid_query_returns_empty():
    """Verify empty/blank query or non-positive top_k returns empty list."""
    dense_mock = MagicMock(spec=BaseRetriever)
    sparse_mock = MagicMock(spec=BM25Retriever)
    hybrid = HybridRetriever(dense_retriever=dense_mock, sparse_retriever=sparse_mock)

    assert hybrid.search("") == []
    assert hybrid.search("   ") == []
    assert hybrid.search("hello", top_k=0) == []
    assert hybrid.search("hello", top_k=-1) == []
    dense_mock.search.assert_not_called()
    sparse_mock.search.assert_not_called()


def test_custom_rrf_k_parameter():
    """Verify custom rrf_k value is used in score computation."""
    chunk1 = _create_chunk("chunk-1")
    dense_mock = MagicMock(spec=BaseRetriever)
    dense_mock.search.return_value = [RetrievalResult(chunk=chunk1, score=1.0)]
    sparse_mock = MagicMock(spec=BM25Retriever)
    sparse_mock.search.return_value = []

    rrf_k = 10
    hybrid = HybridRetriever(dense_retriever=dense_mock, sparse_retriever=sparse_mock, rrf_k=rrf_k)
    results = hybrid.search("query", top_k=5)

    assert len(results) == 1
    assert results[0].score == pytest.approx(1.0 / (10 + 1))


def test_reciprocal_rank_fusion_helper_method():
    """Verify reciprocal_rank_fusion static/class method fuses arbitrary ranking lists."""
    chunk_a = _create_chunk("a")
    chunk_b = _create_chunk("b")

    list1 = [RetrievalResult(chunk=chunk_a, score=0.9)]
    list2 = [RetrievalResult(chunk=chunk_b, score=0.8), RetrievalResult(chunk=chunk_a, score=0.5)]

    fused = HybridRetriever.reciprocal_rank_fusion([list1, list2], rrf_k=60, top_k=2)

    assert len(fused) == 2
    # chunk_a: rank 1 in list1 (1/61) + rank 2 in list2 (1/62)
    assert fused[0].chunk.chunk_id == "a"
    assert fused[0].score == pytest.approx(1.0 / 61 + 1.0 / 62)
    # chunk_b: rank 1 in list2 (1/61)
    assert fused[1].chunk.chunk_id == "b"
    assert fused[1].score == pytest.approx(1.0 / 61)
