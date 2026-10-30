# tests/test_ui_api_client.py
import pytest
from unittest.mock import MagicMock, patch
import httpx
from src.ui.api_client import ApiClient
from src.models import QAResponse, Citation, RetrievalResult, DocumentChunk

def test_check_health_success():
    client = ApiClient(base_url="http://testserver/api/v1")
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = httpx.Response(200, json={"status": "ok", "retrieval_mode": "local"})
        res = client.check_health()
        assert res is not None
        assert res["status"] == "ok"

def test_check_health_connection_error():
    client = ApiClient(base_url="http://testserver/api/v1")
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Failed")):
        res = client.check_health()
        assert res is None

def test_upload_document_success():
    client = ApiClient(base_url="http://testserver/api/v1")
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = httpx.Response(200, json={"filename": "test.pdf", "chunks_indexed": 4, "status": "success"})
        res = client.upload_document(b"%PDF-1.4 dummy", "test.pdf")
        assert res["status"] == "success"
        assert res["chunks_indexed"] == 4

def test_query_success():
    client = ApiClient(base_url="http://testserver/api/v1")
    payload = {
        "answer": "Ap suat bom giam do ro ri van [Tai lieu: pump.pdf, Trang 1].",
        "citations": [{"doc_name": "pump.pdf", "page_number": 1}],
        "abstained": False,
        "retrieved_chunks": []
    }
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = httpx.Response(200, json=payload)
        resp = client.query("Nguyen nhan giam ap suat?", top_k=3)
        assert isinstance(resp, QAResponse)
        assert resp.abstained is False
        assert len(resp.citations) == 1
        assert resp.citations[0].page_number == 1
