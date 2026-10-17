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
    gen = RAGGenerator(llm_client=None)
    raw = "Theo tài liệu, lưu lượng bơm là 50 m3/h [Tài liệu: pump.pdf, Trang 12]."
    response = gen.parse_llm_output(raw_output=raw, retrieved_chunks=[])
    assert response.abstained is False
    assert len(response.citations) == 1
    assert response.citations[0].doc_name == "pump.pdf"
    assert response.citations[0].page_number == 12
