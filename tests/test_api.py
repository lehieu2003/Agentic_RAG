# tests/test_api.py
import io
import pymupdf
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
import docx
from fastapi.testclient import TestClient
from src.api.main import app
from src.config import settings
from src.retrieval.base import BaseRetriever

@pytest.fixture(scope="module", autouse=True)
def isolated_upload_dir(tmp_path_factory):
    upload_dir = tmp_path_factory.mktemp("uploads")
    original = settings.upload_dir
    settings.upload_dir = str(upload_dir)
    yield upload_dir
    settings.upload_dir = original

@pytest.fixture(scope="module")
def client(isolated_upload_dir):
    with TestClient(app) as test_client:
        yield test_client

def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    count = response.json()["vector_store_count"]
    assert count is None or (isinstance(count, int) and count >= 0)

def test_upload_endpoint(client):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Tai lieu huong dan bom ap luc cao. Thong so cong suat 12kW.")
    pdf_bytes = doc.tobytes()
    doc.close()

    response = client.post(
        "/api/v1/upload",
        files={"file": ("test_upload_manual.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["pages_extracted"] == 1
    assert data["chunks_indexed"] >= 1

def test_query_endpoint_structure(client):
    from src.models import QAResponse, Citation
    mock_result = QAResponse(
        answer="Ap suat may bom dat 10 bar theo tai lieu.",
        citations=[Citation(doc_name="test_upload_manual.pdf", page_number=1)],
        abstained=False,
        reasoning_steps=["1. router", "2. search"],
        confidence_score=0.95,
        session_id="test-session",
    )
    with patch.object(app.state.agent, "answer", return_value=mock_result):
        response = client.post("/api/v1/query", json={"question": "Kiem tra ap suat may bom?", "top_k": 3})
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "citations" in data
        assert "abstained" in data

def test_query_without_top_k_uses_system_default(client):
    from src.config import settings
    from src.models import QAResponse
    mock_result = QAResponse(answer="ok", citations=[], abstained=True)
    with patch.object(app.state.agent, "answer", return_value=mock_result) as answer:
        response = client.post("/api/v1/query", json={"question": "Kiem tra ap suat may bom?"})
        assert response.status_code == 200
        assert answer.call_args.kwargs["top_k"] == settings.rerank_top_k

        client.post("/api/v1/query", json={"question": "Kiem tra ap suat may bom?", "top_k": 3})
        assert answer.call_args.kwargs["top_k"] == 3


def test_upload_when_indexing_unsupported_returns_501(client):
    # Mock retriever where index_chunks raises NotImplementedError (like GrpcRetriever)
    mock_retriever = MagicMock(spec=BaseRetriever)
    mock_retriever.index_chunks.side_effect = NotImplementedError("Indexing not supported.")
    original_retriever = app.state.retriever
    app.state.retriever = mock_retriever

    try:
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 72), "Sample text for indexing check.")
        pdf_bytes = doc.tobytes()
        doc.close()

        response = client.post(
            "/api/v1/upload",
            files={"file": ("test_unsupported.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        )
        assert response.status_code == 501
        assert "not supported" in response.json()["detail"].lower()
    finally:
        app.state.retriever = original_retriever

def test_query_returns_503_on_grpc_disconnection(client):
    # Focus #5 requirement: When gRPC service is unavailable, /query returns HTTP 503
    mock_retriever = MagicMock(spec=BaseRetriever)
    mock_retriever.search.side_effect = ConnectionError("Failed to communicate with gRPC RetrievalService")
    original_retriever = app.state.retriever
    app.state.retriever = mock_retriever

    try:
        with patch("src.rag.agent.AgenticRAG._call_llm", return_value=""):
            response = client.post("/api/v1/query", json={"question": "Test disconnected gRPC", "top_k": 3})
            assert response.status_code == 503
            assert "Retrieval failure" in response.json()["detail"]
    finally:
        app.state.retriever = original_retriever


def test_upload_txt_endpoint(client):
    txt_content = "Tai lieu huong dan may nen khi cong nghiep. Van hanh ap luc tieu chuan 8 bar."
    response = client.post(
        "/api/v1/upload",
        files={"file": ("huong_dan.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "huong_dan.txt"
    assert data["pages_extracted"] >= 1
    assert data["chunks_indexed"] >= 1


def test_upload_png_endpoint(client):
    img = Image.new("RGB", (100, 50), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    with patch.object(app.state.ocr_engine, "extract_text_from_image", return_value="Thong so so do mach dien"):
        response = client.post(
            "/api/v1/upload",
            files={"file": ("mach_dien.png", buf, "image/png")}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "mach_dien.png"
    assert data["pages_extracted"] == 1
    assert data["pages_scanned_ocr"] == 1
    assert data["chunks_indexed"] >= 1


def test_upload_docx_endpoint(client):
    doc = docx.Document()
    doc.add_paragraph("Thong so ky thuat may bien ap 110kV.")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    response = client.post(
        "/api/v1/upload",
        files={"file": ("bien_ap.docx", buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "bien_ap.docx"
    assert data["pages_extracted"] >= 1
    assert data["chunks_indexed"] >= 1


def test_upload_unsupported_format_returns_400(client):
    zip_bytes = b"PK\x03\x04fake_zip_content"
    response = client.post(
        "/api/v1/upload",
        files={"file": ("archive.zip", io.BytesIO(zip_bytes), "application/zip")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file format" in data["detail"]


def test_upload_corrupt_docx_returns_400(client):
    corrupt_bytes = b"not a valid docx"
    response = client.post(
        "/api/v1/upload",
        files={"file": ("corrupted.docx", io.BytesIO(corrupt_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "Failed to extract text" in data["detail"] or "Corrupted or unreadable document" in data["detail"]


