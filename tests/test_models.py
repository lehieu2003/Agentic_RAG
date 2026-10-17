# tests/test_models.py
from src.models import DocumentChunk, RetrievalResult, Citation, QAResponse
from src.config import Settings

def test_document_chunk_validation():
    chunk = DocumentChunk(
        chunk_id="chk_1",
        doc_name="pump_manual.pdf",
        page_number=1,
        text="Máy bơm hoạt động ở công suất 5kW.",
        metadata={"author": "TKE"}
    )
    assert chunk.page_number == 1
    assert chunk.doc_name == "pump_manual.pdf"

def test_qa_response_schema():
    resp = QAResponse(
        answer="Áp suất giảm do hỏng van.",
        citations=[Citation(doc_name="pump.pdf", page_number=3)],
        abstained=False,
        retrieved_chunks=[]
    )
    assert resp.abstained is False
    assert len(resp.citations) == 1

def test_default_settings():
    settings = Settings()
    assert settings.retrieval_mode in ["local", "grpc"]

