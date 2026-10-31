"""Tests for CrossEncoderReranker covering lazy loading, scoring, sorting, and edge cases."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from src.models import DocumentChunk, RetrievalResult
from src.retrieval.reranker import CrossEncoderReranker


def _create_candidate(chunk_id: str, text: str, initial_score: float = 0.5) -> RetrievalResult:
    return RetrievalResult(
        chunk=DocumentChunk(
            chunk_id=chunk_id,
            doc_name="manual.pdf",
            page_number=1,
            text=text,
        ),
        score=initial_score,
    )


def test_lazy_initialization():
    """Verify CrossEncoder is NOT loaded until first rerank() call with non-empty candidates."""
    with patch("sentence_transformers.CrossEncoder") as mock_ce_cls:
        mock_instance = MagicMock()
        mock_instance.predict.return_value = np.array([0.9])
        mock_ce_cls.return_value = mock_instance

        reranker = CrossEncoderReranker(model_name="BAAI/bge-reranker-base")
        assert reranker._model is None
        assert mock_ce_cls.call_count == 0

        # Rerank triggers lazy initialization
        candidate = _create_candidate("chk_1", "Sample text")
        results = reranker.rerank(query="test query", candidates=[candidate], top_k=5)

        assert mock_ce_cls.call_count == 1
        assert reranker._model is not None
        assert len(results) == 1


def test_rerank_scoring_and_descending_sorting():
    """Verify scores are accurately reassigned and candidates sorted descending."""
    candidates = [
        _create_candidate("chk_A", "Text A", initial_score=0.9),
        _create_candidate("chk_B", "Text B", initial_score=0.5),
        _create_candidate("chk_C", "Text C", initial_score=0.1),
    ]

    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([-1.5, 3.2, 0.8])

    reranker = CrossEncoderReranker()
    reranker._model = mock_model

    results = reranker.rerank(query="van điều áp", candidates=candidates, top_k=3)

    assert len(results) == 3
    # Check descending order: chk_B (3.2), chk_C (0.8), chk_A (-1.5)
    assert results[0].chunk.chunk_id == "chk_B"
    assert pytest.approx(results[0].score, 0.001) == 3.2

    assert results[1].chunk.chunk_id == "chk_C"
    assert pytest.approx(results[1].score, 0.001) == 0.8

    assert results[2].chunk.chunk_id == "chk_A"
    assert pytest.approx(results[2].score, 0.001) == -1.5


def test_rerank_top_k_truncation():
    """Verify results are truncated strictly to top_k."""
    candidates = [
        _create_candidate(f"chk_{i}", f"Text {i}", initial_score=0.1 * i)
        for i in range(5)
    ]

    mock_model = MagicMock()
    # Scores for chk_0..chk_4
    mock_model.predict.return_value = np.array([1.0, 5.0, 3.0, 2.0, 4.0])

    reranker = CrossEncoderReranker()
    reranker._model = mock_model

    results = reranker.rerank(query="quy trình bảo dưỡng", candidates=candidates, top_k=2)

    assert len(results) == 2
    assert results[0].chunk.chunk_id == "chk_1"  # score 5.0
    assert results[1].chunk.chunk_id == "chk_4"  # score 4.0


def test_rerank_empty_candidates_safety():
    """Verify empty candidates returns empty list without calling model."""
    mock_model = MagicMock()
    reranker = CrossEncoderReranker()
    reranker._model = mock_model

    results = reranker.rerank(query="thông số kỹ thuật", candidates=[], top_k=5)

    assert results == []
    mock_model.predict.assert_not_called()


def test_rerank_empty_or_whitespace_query_safety():
    """Verify empty or whitespace query returns empty list without calling model."""
    candidates = [_create_candidate("chk_1", "Some content")]
    mock_model = MagicMock()
    reranker = CrossEncoderReranker()
    reranker._model = mock_model

    assert reranker.rerank(query="", candidates=candidates, top_k=5) == []
    assert reranker.rerank(query="   ", candidates=candidates, top_k=5) == []
    assert reranker.rerank(query=None, candidates=candidates, top_k=5) == []
    mock_model.predict.assert_not_called()


def test_rerank_single_candidate():
    """Verify single candidate handling with float/1D array prediction."""
    candidate = _create_candidate("chk_single", "Đặc tính lưu lượng bơm")

    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([1.87])

    reranker = CrossEncoderReranker()
    reranker._model = mock_model

    results = reranker.rerank(query="lưu lượng bơm", candidates=[candidate], top_k=5)

    assert len(results) == 1
    assert results[0].chunk.chunk_id == "chk_single"
    assert pytest.approx(results[0].score, 0.001) == 1.87


def test_rerank_invalid_top_k():
    """Verify top_k <= 0 returns empty list without calling model."""
    candidate = _create_candidate("chk_1", "Text")
    mock_model = MagicMock()
    reranker = CrossEncoderReranker()
    reranker._model = mock_model

    assert reranker.rerank("query", [candidate], top_k=0) == []
    assert reranker.rerank("query", [candidate], top_k=-2) == []
    mock_model.predict.assert_not_called()


def test_rerank_query_passage_pairs_format():
    """Verify query-passage pairs passed to CrossEncoder.predict are formatted correctly."""
    candidates = [
        _create_candidate("chk_1", "Nội dung đoạn 1"),
        _create_candidate("chk_2", "Nội dung đoạn 2"),
    ]

    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([0.5, 0.9])

    reranker = CrossEncoderReranker()
    reranker._model = mock_model

    reranker.rerank(query="câu hỏi kiểm tra", candidates=candidates, top_k=2)

    mock_model.predict.assert_called_once_with([
        ("câu hỏi kiểm tra", "Nội dung đoạn 1"),
        ("câu hỏi kiểm tra", "Nội dung đoạn 2"),
    ])


def test_reranker_custom_model_and_device():
    """Verify custom model_name and device are forwarded when initializing CrossEncoder."""
    with patch("sentence_transformers.CrossEncoder") as mock_ce_cls:
        mock_instance = MagicMock()
        mock_instance.predict.return_value = np.array([0.7])
        mock_ce_cls.return_value = mock_instance

        reranker = CrossEncoderReranker(model_name="custom/reranker-model", device="cpu")
        candidate = _create_candidate("chk_1", "Some passage")
        reranker.rerank(query="query", candidates=[candidate], top_k=1)

        mock_ce_cls.assert_called_once_with("custom/reranker-model", device="cpu")


def test_export_from_retrieval_package():
    """Verify CrossEncoderReranker is exported in src.retrieval."""
    from src.retrieval import CrossEncoderReranker as ExportedReranker

    assert ExportedReranker is CrossEncoderReranker

