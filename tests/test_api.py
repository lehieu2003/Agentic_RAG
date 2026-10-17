# tests/test_api.py
import io
import pymupdf
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from src.api.main import app
from src.retrieval.base import BaseRetriever

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

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
    response = client.post("/api/v1/query", json={"question": "Kiem tra ap suat may bom?", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "citations" in data
    assert "abstained" in data

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
        response = client.post("/api/v1/query", json={"question": "Test disconnected gRPC", "top_k": 3})
        assert response.status_code == 503
        assert "Retrieval failure" in response.json()["detail"]
    finally:
        app.state.retriever = original_retriever
