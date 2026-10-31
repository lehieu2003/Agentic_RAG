# tests/test_rag.py
from src.models import DocumentChunk, RetrievalResult
from src.rag.prompt import build_rag_prompt, ABSTAIN_PHRASE
from src.rag.generator import RAGGenerator

def test_prompt_formatting():
    chunks = [
        RetrievalResult(
            chunk=DocumentChunk(chunk_id="c1", doc_name="pump.pdf", page_number=12, text="Lưu lượng thiết kế 50 m3/h."),
            score=0.88
        )
    ]
    prompt = build_rag_prompt(question="Lưu lượng là bao nhiêu?", chunks=chunks)
    assert "[Tài liệu: pump.pdf | Trang: 12]" in prompt
    assert "Lưu lượng thiết kế 50 m3/h." in prompt
    assert ABSTAIN_PHRASE in prompt

def test_abstention_handling():
    gen = RAGGenerator(llm_client=None)  # Mock or deterministic mode
    response = gen.parse_llm_output(
        raw_output=f"{ABSTAIN_PHRASE}",
        retrieved_chunks=[]
    )
    assert response.abstained is True
    assert ABSTAIN_PHRASE in response.answer
    assert len(response.citations) == 0

def test_citation_parsing():
    chunk = RetrievalResult(
        chunk=DocumentChunk(chunk_id="c1", doc_name="pump.pdf", page_number=12, text="Lưu lượng..."),
        score=0.9
    )
    gen = RAGGenerator(llm_client=None)
    raw = "Theo tài liệu, lưu lượng bơm là 50 m3/h [Tài liệu: pump.pdf, Trang 12]."
    response = gen.parse_llm_output(raw_output=raw, retrieved_chunks=[chunk])
    assert response.abstained is False
    assert len(response.citations) == 1
    assert response.citations[0].doc_name == "pump.pdf"
    assert response.citations[0].page_number == 12

def test_citation_grounding_rejects_hallucinated_citations():
    # Only pump.pdf p.12 was retrieved
    retrieved = [
        RetrievalResult(
            chunk=DocumentChunk(chunk_id="c1", doc_name="pump.pdf", page_number=12, text="van an toan"),
            score=0.85
        )
    ]
    gen = RAGGenerator(llm_client=None)
    # LLM hallucinates a citation from manual.pdf p.99 which was NOT in context
    raw_with_hallucination = "Áp suất 10 bar [Tài liệu: manual.pdf, Trang 99]."
    response = gen.parse_llm_output(raw_output=raw_with_hallucination, retrieved_chunks=retrieved)

    # Hallucinated citation must be rejected
    assert len(response.citations) == 0
    # Ungrounded answer triggers abstention
    assert response.abstained is True
    assert ABSTAIN_PHRASE in response.answer

def test_abstention_on_low_relevance_query():
    # Chunks with relevance below 0.55 should trigger abstention immediately
    low_score_chunk = [
        RetrievalResult(
            chunk=DocumentChunk(chunk_id="c1", doc_name="pump.pdf", page_number=1, text="van xa"),
            score=0.52  # Below 0.55 threshold
        )
    ]
    gen = RAGGenerator(llm_client=None, min_relevance_score=0.55)
    response = gen.generate_answer("Giá cổ phiếu Apple hôm nay?", low_score_chunk)
    assert response.abstained is True
    assert ABSTAIN_PHRASE in response.answer


def test_citation_unicode_normalization_and_flexible_matching():
    import unicodedata
    # NFD decomposed doc_name as saved by MacOS APFS
    nfd_name = unicodedata.normalize("NFD", "#19 - GraphRAG - Từ văn bản tới Knowledge Graph.pdf")
    chunk = RetrievalResult(
        chunk=DocumentChunk(chunk_id="c1", doc_name=nfd_name, page_number=4, text="GraphRAG definition"),
        score=0.95
    )
    gen = RAGGenerator(llm_client=None)

    # 1. NFC citation format
    raw_nfc = "GraphRAG bổ sung cấu trúc đồ thị [Tài liệu: #19 - GraphRAG - Từ văn bản tới Knowledge Graph.pdf, Trang 4]."
    resp1 = gen.parse_llm_output(raw_nfc, retrieved_chunks=[chunk])
    assert resp1.abstained is False
    assert len(resp1.citations) == 1
    assert resp1.citations[0].page_number == 4

    # 2. Omitted prefix
    raw_no_prefix = "GraphRAG [Tài liệu: GraphRAG - Từ văn bản tới Knowledge Graph.pdf, Trang 4]."
    resp2 = gen.parse_llm_output(raw_no_prefix, retrieved_chunks=[chunk])
    assert resp2.abstained is False
    assert len(resp2.citations) == 1

    # 3. Omitted extension and different separator syntax
    raw_no_ext = "GraphRAG [Tài liệu: #19 - GraphRAG - Từ văn bản tới Knowledge Graph | Trang: 4]."
    resp3 = gen.parse_llm_output(raw_no_ext, retrieved_chunks=[chunk])
    assert resp3.abstained is False
    assert len(resp3.citations) == 1
