# tests/test_file_storage.py
import io
import pymupdf
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from src.api.main import app
from src.config import settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Provide a test client with an isolated temporary upload directory."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "upload_dir", str(upload_dir))
    with TestClient(app) as test_client:
        yield test_client


def _make_pdf(text: str = "Tài liệu kiểm tra lưu trữ và phục vụ.") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_upload_persists_raw_file(client, tmp_path):
    pdf_bytes = _make_pdf("Thử nghiệm lưu trữ file gốc vĩnh viễn.")
    filename = "test_persist.pdf"

    response = client.post(
        "/api/v1/upload",
        files={"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == filename

    saved_path = Path(settings.upload_dir) / filename
    assert saved_path.exists()
    assert saved_path.is_file()
    assert saved_path.read_bytes() == pdf_bytes


def test_upload_duplicate_file_skips_indexing(client):
    pdf_bytes = _make_pdf("Thử nghiệm phát hiện file trùng lặp.")
    filename = "test_duplicate.pdf"

    # First upload - should succeed and index
    resp1 = client.post(
        "/api/v1/upload",
        files={"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "success"
    assert data1["chunks_indexed"] >= 1

    # Second upload with identical filename - should be deduplicated
    resp2 = client.post(
        "/api/v1/upload",
        files={"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "already_exists"
    assert data2["chunks_indexed"] == 0
    assert data2["pages_extracted"] == 0
    assert "tồn tại" in data2.get("message", "").lower() or "already" in data2.get("message", "").lower()


def test_serve_file_success(client):
    pdf_bytes = _make_pdf("Thử nghiệm xem tài liệu trực tiếp trên trình duyệt.")
    filename = "test_serve.pdf"

    upload_resp = client.post(
        "/api/v1/upload",
        files={"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_resp.status_code == 200

    resp = client.get(f"/api/v1/files/{filename}")
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers.get("content-type", "")
    assert f'inline; filename="{filename}"' in resp.headers.get("content-disposition", "")
    assert resp.content == pdf_bytes


def test_serve_file_path_traversal_rejected(client):
    # Non-existent file
    resp_missing = client.get("/api/v1/files/nonexistent.pdf")
    assert resp_missing.status_code == 404

    # Path traversal attempts
    resp_traversal1 = client.get("/api/v1/files/..%2F..%2Fetc%2Fpasswd")
    assert resp_traversal1.status_code in [400, 404]

    resp_traversal2 = client.get("/api/v1/files/../../test.txt")
    assert resp_traversal2.status_code in [400, 404]


def test_list_files_endpoint(client):
    # Upload doc 1
    pdf_bytes = _make_pdf("Tài liệu một")
    client.post("/api/v1/upload", files={"file": ("doc1.pdf", io.BytesIO(pdf_bytes), "application/pdf")})

    # Upload doc 2
    txt_content = "Nội dung tài liệu văn bản thuần hai."
    client.post("/api/v1/upload", files={"file": ("doc2.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")})

    resp = client.get("/api/v1/files")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    filenames = [f["filename"] for f in data]
    assert "doc1.pdf" in filenames
    assert "doc2.txt" in filenames

    doc1_info = next(f for f in data if f["filename"] == "doc1.pdf")
    assert doc1_info["size_bytes"] == len(pdf_bytes)
    assert doc1_info["file_type"] == ".pdf"
    assert "uploaded_at" in doc1_info

    doc2_info = next(f for f in data if f["filename"] == "doc2.txt")
    assert doc2_info["size_bytes"] == len(txt_content.encode("utf-8"))
    assert doc2_info["file_type"] == ".txt"


def test_delete_file_endpoint(client, tmp_path):
    upload_dir = tmp_path / "uploads"

    # Upload a document
    txt_content = "Tài liệu kiểm thử xoá."
    upload_resp = client.post(
        "/api/v1/upload",
        files={"file": ("to_delete.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")}
    )
    assert upload_resp.status_code == 200
    assert (upload_dir / "to_delete.txt").is_file()

    # Call DELETE /api/v1/files/to_delete.txt
    del_resp = client.delete("/api/v1/files/to_delete.txt")
    assert del_resp.status_code == 200
    del_data = del_resp.json()
    assert del_data["status"] == "success"
    assert del_data["file_deleted"] is True

    # Verify physical file is gone
    assert not (upload_dir / "to_delete.txt").exists()

    # Verify list_files no longer contains it
    list_resp = client.get("/api/v1/files")
    filenames = [f["filename"] for f in list_resp.json()]
    assert "to_delete.txt" not in filenames
