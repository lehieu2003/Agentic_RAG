"""Tests for Sparse BM25 Retriever."""

import pytest
from src.models import DocumentChunk
from src.retrieval.base import BaseRetriever
from src.retrieval.bm25 import BM25Retriever


def test_bm25_conforms_to_base_retriever():
    retriever = BM25Retriever()
    assert isinstance(retriever, BaseRetriever)


def test_tokenization_preserves_technical_codes():
    retriever = BM25Retriever()
    
    assert retriever.tokenize("TCVN 9222:2012") == ["tcvn", "9222", ":", "2012"]
    assert retriever.tokenize("ISO 9906:1999") == ["iso", "9906", ":", "1999"]
    assert retriever.tokenize("TKE-380") == ["tke", "-", "380"]
    assert retriever.tokenize("Điều 24") == ["điều", "24"]
    assert retriever.tokenize("QCVN 01-1:2018/BYT") == ["qcvn", "01", "-", "1", ":", "2018", "/", "byt"]
    assert retriever.tokenize("") == []
    assert retriever.tokenize("   \n\t  ") == []


def test_bm25_exact_matching():
    chunk1 = DocumentChunk(
        chunk_id="c1",
        doc_name="tcvn_9222.pdf",
        page_number=1,
        text="Tiêu chuẩn kỹ thuật TCVN 9222:2012 về phương pháp đo kiểm máy bơm công nghiệp."
    )
    chunk2 = DocumentChunk(
        chunk_id="c2",
        doc_name="manual_tke.pdf",
        page_number=5,
        text="Thông số kỹ thuật model máy bơm ly tâm TKE-380 dải lưu lượng lớn."
    )
    chunk3 = DocumentChunk(
        chunk_id="c3",
        doc_name="safety.pdf",
        page_number=10,
        text="Quy định an toàn lao động trong nhà xưởng và phòng chống cháy nổ."
    )

    retriever = BM25Retriever([chunk1, chunk2, chunk3])

    # Search for standard code
    results_std = retriever.search("TCVN 9222:2012", top_k=5)
    assert len(results_std) >= 1
    assert results_std[0].chunk.chunk_id == "c1"
    assert results_std[0].score == 1.0
    assert 0.0 <= results_std[0].score <= 1.0

    # Search for model identifier
    results_model = retriever.search("TKE-380", top_k=5)
    assert len(results_model) >= 1
    assert results_model[0].chunk.chunk_id == "c2"
    assert results_model[0].score == 1.0
    assert 0.0 <= results_model[0].score <= 1.0


def test_bm25_ranking_and_score_normalization():
    chunk_high = DocumentChunk(
        chunk_id="high",
        doc_name="pump_eval.pdf",
        page_number=2,
        text="Kiểm tra rung động máy bơm ly tâm. Đo rung động máy bơm ly tâm theo chu kỳ định kỳ."
    )
    chunk_low = DocumentChunk(
        chunk_id="low",
        doc_name="general_maintenance.pdf",
        page_number=3,
        text="Quy trình bảo trì chung định kỳ máy bơm."
    )
    chunk_unrelated = DocumentChunk(
        chunk_id="none",
        doc_name="office.pdf",
        page_number=1,
        text="Hợp đồng văn phòng và văn phòng phẩm hành chính."
    )

    retriever = BM25Retriever([chunk_high, chunk_low, chunk_unrelated])
    results = retriever.search("đo rung động máy bơm ly tâm", top_k=3)

    assert len(results) >= 2
    assert results[0].chunk.chunk_id == "high"
    assert results[1].chunk.chunk_id == "low"
    assert results[0].score >= results[1].score
    assert results[0].score == 1.0
    assert 0.0 <= results[1].score <= 1.0


def test_bm25_empty_index_safety():
    retriever = BM25Retriever()
    assert retriever.search("TCVN 9222:2012") == []
    assert retriever.search("") == []


def test_bm25_empty_query_safety():
    chunk = DocumentChunk(
        chunk_id="c1",
        doc_name="test.pdf",
        page_number=1,
        text="Nội dung thử nghiệm tài liệu kỹ thuật."
    )
    retriever = BM25Retriever([chunk])
    assert retriever.search("") == []
    assert retriever.search("   \n\t  ") == []


def test_bm25_no_matching_terms():
    chunk = DocumentChunk(
        chunk_id="c1",
        doc_name="test.pdf",
        page_number=1,
        text="Nội dung thử nghiệm tài liệu kỹ thuật."
    )
    retriever = BM25Retriever([chunk])
    results = retriever.search("xyz_non_existent_token_12345")
    assert results == []


def test_bm25_dynamic_index_chunks():
    retriever = BM25Retriever()
    chunk1 = DocumentChunk(
        chunk_id="c1",
        doc_name="doc1.pdf",
        page_number=1,
        text="Tiêu chuẩn TCVN 9222:2012 về thử nghiệm máy bơm."
    )
    indexed_count = retriever.index_chunks([chunk1])
    assert indexed_count == 1

    res = retriever.search("TCVN 9222:2012")
    assert len(res) == 1
    assert res[0].chunk.chunk_id == "c1"

    chunk2 = DocumentChunk(
        chunk_id="c2",
        doc_name="doc2.pdf",
        page_number=2,
        text="Thiết bị máy bơm ly tâm model TKE-380."
    )
    indexed_count2 = retriever.index_chunks([chunk2])
    assert indexed_count2 == 1

    res2 = retriever.search("TKE-380")
    assert len(res2) == 1
    assert res2[0].chunk.chunk_id == "c2"

    # Ensure previous chunk is still searchable
    res1_again = retriever.search("TCVN 9222:2012")
    assert len(res1_again) == 1
    assert res1_again[0].chunk.chunk_id == "c1"
