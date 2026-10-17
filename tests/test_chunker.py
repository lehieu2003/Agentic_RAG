# tests/test_chunker.py
from src.ingestion.chunker import chunk_document
from src.models import DocumentChunk

def test_chunk_preserves_page_metadata():
    pages = [
        {
            "doc_name": "manual.pdf",
            "page_number": 1,
            "text": "Đoạn văn ngắn của trang 1."
        },
        {
            "doc_name": "manual.pdf",
            "page_number": 2,
            "text": "Nội dung rất dài của trang 2. " * 30  # > 500 chars
        }
    ]
    chunks = chunk_document(pages, chunk_size=300, chunk_overlap=30)
    assert len(chunks) >= 3
    # Mọi chunk phải có doc_name và page_number chính xác
    assert chunks[0].page_number == 1
    assert chunks[0].doc_name == "manual.pdf"
    assert chunks[1].page_number == 2
    assert chunks[1].doc_name == "manual.pdf"
    assert all(isinstance(c, DocumentChunk) for c in chunks)
    # Kiểm tra chunk_id không rỗng và duy nhất
    chunk_ids = [c.chunk_id for c in chunks]
    assert len(chunk_ids) == len(set(chunk_ids))

