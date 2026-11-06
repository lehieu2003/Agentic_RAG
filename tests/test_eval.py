# tests/test_eval.py
import json
import math
from typing import Dict, List

import pytest

from src.models import Citation, DocumentChunk, QAResponse, RetrievalResult
from src.eval.metrics import (
    calculate_citation_precision,
    calculate_mrr_at_k,
    calculate_ndcg_at_k,
    calculate_recall_at_k,
    calculate_token_f1,
    evaluate_abstention,
)
from src.eval.runner import run_benchmark
from src.rag.generator import RAGGenerator
from src.retrieval.base import BaseRetriever

class MockRetriever(BaseRetriever):
    def search(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        # Return chunks matching query keywords or fallback
        if "áp suất" in query.lower():
            chunk = DocumentChunk(chunk_id="c1", doc_name="pump_maintenance_guide.pdf", page_number=1, text="áp suất")
        else:
            chunk = DocumentChunk(chunk_id="c2", doc_name="pump_maintenance_guide.pdf", page_number=2, text="van an toan")
        return [RetrievalResult(chunk=chunk, score=0.9)]

def test_recall_at_k_hit():
    chunks = [
        RetrievalResult(chunk=DocumentChunk(chunk_id="c1", doc_name="pump.pdf", page_number=5, text="A"), score=0.9),
        RetrievalResult(chunk=DocumentChunk(chunk_id="c2", doc_name="pump.pdf", page_number=12, text="B"), score=0.8),
        RetrievalResult(chunk=DocumentChunk(chunk_id="c3", doc_name="pump.pdf", page_number=20, text="C"), score=0.7),
    ]
    # K=1: Trang 12 chưa xuất hiện -> 0.0
    assert calculate_recall_at_k(chunks, expected_doc="pump.pdf", expected_pages=[12], k=1) == 0.0
    # K=2: Trang 12 xuất hiện ở vị trí thứ 2 -> 1.0
    assert calculate_recall_at_k(chunks, expected_doc="pump.pdf", expected_pages=[12], k=2) == 1.0

def test_abstention_metric():
    assert evaluate_abstention(should_abstain=True, actually_abstained=True) is True
    assert evaluate_abstention(should_abstain=False, actually_abstained=True) is False

def test_run_benchmark_without_generator():
    retriever = MockRetriever()
    report = run_benchmark(retriever, ground_truth_file="tests/fixtures/sample_ground_truth.json", k_values=[1, 3])
    assert "recall@1" in report
    assert "recall@3" in report
    assert report["abstention_accuracy"] is None
    assert "markdown_report" in report
    assert report["total_queries"] == 15

def test_run_benchmark_with_generator():
    retriever = MockRetriever()
    generator = RAGGenerator(provider="mock")
    report = run_benchmark(retriever, ground_truth_file="tests/fixtures/sample_ground_truth.json", k_values=[1, 3], rag_generator=generator)
    assert report["abstention_accuracy"] is not None
    assert "Abstention Accuracy" in report["markdown_report"]


class MappedRetriever(BaseRetriever):
    """Retriever returning a fixed ranked list per query for deterministic tests."""

    def __init__(self, mapping: Dict[str, List[RetrievalResult]]):
        self.mapping = mapping

    def search(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        return self.mapping.get(query, [])[:top_k]


def _chunk(doc_name: str, page_number: int, chunk_id: str = "c1") -> RetrievalResult:
    return RetrievalResult(
        chunk=DocumentChunk(
            chunk_id=chunk_id,
            doc_name=doc_name,
            page_number=page_number,
            text="text",
        ),
        score=1.0,
    )


def test_mrr_and_ndcg_at_k():
    chunks = [
        _chunk("pump.pdf", 5, "c1"),
        _chunk("pump.pdf", 12, "c2"),
        _chunk("pump.pdf", 20, "c3"),
    ]
    assert calculate_mrr_at_k(chunks, "pump.pdf", [12], k=1) == 0.0
    assert calculate_mrr_at_k(chunks, "pump.pdf", [12], k=2) == 0.5
    assert calculate_mrr_at_k(chunks, "pump.pdf", [99], k=3) == 0.0

    assert calculate_ndcg_at_k(chunks, "pump.pdf", [12], k=1) == 0.0
    assert calculate_ndcg_at_k(chunks, "pump.pdf", [12], k=2) == pytest.approx(1.0 / math.log2(3))
    assert calculate_ndcg_at_k(chunks, "pump.pdf", [12], k=3) == pytest.approx(1.0 / math.log2(3))


def test_metrics_normalize_doc_names():
    chunks = [_chunk("Tài Liệu.PDF", 1)]
    assert calculate_recall_at_k(chunks, "tài liệu.pdf", [1], k=1) == 1.0
    assert calculate_mrr_at_k(chunks, "tài liệu.pdf", [1], k=1) == 1.0


def test_token_f1():
    assert calculate_token_f1("Áp suất 10 bar", "áp suất 10 bar") == 1.0
    assert calculate_token_f1("", "") == 1.0
    assert calculate_token_f1("hoàn toàn khác", "áp suất 10 bar") == 0.0
    assert calculate_token_f1("áp suất 10 bar", "áp suất 12 bar") == pytest.approx(0.75)


def test_citation_precision_grounding():
    retrieved = [_chunk("pump.pdf", 1), _chunk("pump.pdf", 2)]
    citations = [
        Citation(doc_name="pump.pdf", page_number=1),
        Citation(doc_name="pump.pdf", page_number=9),
    ]
    assert calculate_citation_precision(citations, retrieved) == 0.5
    assert calculate_citation_precision([], retrieved) == 1.0
    assert calculate_citation_precision([Citation(doc_name="pump.pdf", page_number=1)], []) == 0.0


def test_run_benchmark_with_answer_fn_and_buckets(tmp_path):
    dataset = [
        {
            "id": "q1",
            "question": "Q1",
            "expected_doc": "pump.pdf",
            "expected_pages": [1],
            "ground_truth_answer": "áp suất 10 bar",
            "should_abstain": False,
            "bucket": "vi2vi",
        },
        {
            "id": "q2",
            "question": "Q2",
            "expected_doc": "manual_en.pdf",
            "expected_pages": [2],
            "ground_truth_answer": "Working pressure is 10 bar",
            "should_abstain": False,
            "bucket": "vi2en",
        },
        {
            "id": "q3",
            "question": "Q3",
            "expected_doc": None,
            "expected_pages": [],
            "ground_truth_answer": "Abstain",
            "should_abstain": True,
        },
    ]
    gt_path = tmp_path / "ground_truth.json"
    gt_path.write_text(json.dumps(dataset), encoding="utf-8")

    retriever = MappedRetriever(
        {
            "Q1": [_chunk("pump.pdf", 1, "c1")],
            "Q2": [_chunk("other.pdf", 1, "c_other"), _chunk("manual_en.pdf", 2, "c2")],
            "Q3": [],
        }
    )

    def answer_fn(question: str) -> QAResponse:
        if question == "Q1":
            return QAResponse(
                answer="Áp suất là 10 bar",
                citations=[Citation(doc_name="pump.pdf", page_number=1)],
            )
        if question == "Q2":
            return QAResponse(
                answer="Working pressure is 10 bar",
                citations=[Citation(doc_name="manual_en.pdf", page_number=2)],
            )
        return QAResponse(
            answer="Tôi không tìm thấy thông tin này trong tài liệu được cung cấp.",
            abstained=True,
        )

    output_path = tmp_path / "report.json"
    report = run_benchmark(
        retriever,
        ground_truth_file=str(gt_path),
        k_values=[1, 3],
        answer_fn=answer_fn,
        output_json=str(output_path),
    )

    assert report["recall@1"] == 0.5
    assert report["recall@3"] == 1.0
    assert report["mrr@1"] == 0.5
    assert report["mrr@3"] == pytest.approx(0.75)
    assert report["citation_precision"] == 1.0
    assert report["answer_f1"] == pytest.approx((0.8889 + 1.0) / 2, abs=1e-3)
    assert report["abstention_accuracy"] == 1.0
    assert report["in_scope_abstention_rate"] == 0.0
    assert report["bucket_metrics"]["vi2vi"]["recall@1"] == 1.0
    assert report["bucket_metrics"]["vi2en"]["recall@1"] == 0.0
    assert len(report["per_query"]) == 3

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert "summary" in persisted
    assert len(persisted["per_query"]) == 3
    assert persisted["summary"]["bucket_metrics"]["vi2en"]["num_queries"] == 1


def test_citation_precision_uses_agent_retrieved_chunks(tmp_path):
    dataset = [
        {
            "id": "q1",
            "question": "Q1",
            "expected_doc": "other.pdf",
            "expected_pages": [1],
            "ground_truth_answer": "answer",
            "should_abstain": False,
        }
    ]
    gt_path = tmp_path / "ground_truth.json"
    gt_path.write_text(json.dumps(dataset), encoding="utf-8")

    initial_retrieved = [_chunk("other.pdf", 1)]
    agent_retrieved = [_chunk("pump.pdf", 3)]

    def answer_fn(_: str) -> QAResponse:
        return QAResponse(
            answer="answer",
            citations=[Citation(doc_name="pump.pdf", page_number=3)],
            retrieved_chunks=agent_retrieved,
        )

    report = run_benchmark(
        MappedRetriever({"Q1": initial_retrieved}),
        ground_truth_file=str(gt_path),
        k_values=[1],
        answer_fn=answer_fn,
    )

    # The cited chunk came from the agent's expanded retrieval, not the initial list.
    assert report["citation_precision"] == 1.0
    assert report["answer_f1"] == 1.0
