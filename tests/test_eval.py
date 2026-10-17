# tests/test_eval.py
from typing import List
from src.models import DocumentChunk, RetrievalResult
from src.eval.metrics import calculate_recall_at_k, evaluate_abstention
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
    report = run_benchmark(retriever, ground_truth_file="data/eval/ground_truth.json", k_values=[1, 3])
    assert "recall@1" in report
    assert "recall@3" in report
    assert report["abstention_accuracy"] is None
    assert "markdown_report" in report
    assert report["total_queries"] == 15

def test_run_benchmark_with_generator():
    retriever = MockRetriever()
    generator = RAGGenerator(provider="mock")
    report = run_benchmark(retriever, ground_truth_file="data/eval/ground_truth.json", k_values=[1, 3], rag_generator=generator)
    assert report["abstention_accuracy"] is not None
    assert "Abstention Accuracy" in report["markdown_report"]
