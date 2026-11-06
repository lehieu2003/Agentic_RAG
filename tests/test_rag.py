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


def test_calculation_prompt_guidance():
    chunk = RetrievalResult(
        chunk=DocumentChunk(
            chunk_id="c1",
            doc_name="pump.pdf",
            page_number=8,
            text="Hệ số Reynolds Re = (U * D) / nu. Trong đó U là vận tốc, D là đường kính, nu là độ nhớt."
        ),
        score=0.92
    )
    prompt = build_rag_prompt("Tính Reynolds khi D = 0.2 m, U = 2 m/s", [chunk])
    assert "HƯỚNG DẪN TÍNH TOÁN KỸ THUẬT" in prompt
    assert "pi*D^2/4" in prompt or "Thế số và tính toán" in prompt
    assert "[Tài liệu: pump.pdf | Trang: 8]" in prompt


def test_parse_llm_output_strips_inline_citation_markers():
    from src.models import DocumentChunk, RetrievalResult
    gen = RAGGenerator(llm_client=None)
    chunk = DocumentChunk(chunk_id="c8", doc_name="tài liệu máy bơm.pdf", page_number=8, text="Re = U·D/ν")
    raw = (
        "Cần các thông số sau, ngoài $D = 0,15$ m [Tài liệu: tài liệu máy bơm.pdf, Trang 8]:\n"
        "1. **Vận tốc** $U$ [Tài liệu: tài liệu máy bơm.pdf, Trang 8].\n"
        "Công thức: $Re = \\frac{U D}{\\nu}$ [tài liệu máy bơm.pdf (Trang 8)]"
    )
    resp = gen.parse_llm_output(raw, retrieved_chunks=[RetrievalResult(chunk=chunk, score=0.9)])
    assert not resp.abstained
    assert [(c.doc_name, c.page_number) for c in resp.citations] == [("tài liệu máy bơm.pdf", 8)]
    assert "Trang 8" not in resp.answer
    assert resp.answer == (
        "Cần các thông số sau, ngoài $D = 0,15$ m:\n"
        "1. **Vận tốc** $U$.\n"
        "Công thức: $Re = \\frac{U D}{\\nu}$"
    )


def test_strip_citation_markers_keeps_non_citation_brackets():
    gen = RAGGenerator(llm_client=None)
    text = "Xem [hướng dẫn](https://x.io), mảng [1, 2], công thức \\[a+b\\] và [Trang 4]."
    assert gen.strip_citation_markers(text) == "Xem [hướng dẫn](https://x.io), mảng [1, 2], công thức \\[a+b\\] và."
