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


def test_chunk_preserves_sentence_boundaries_and_nfc_doc_name():
    import unicodedata
    nfd_name = unicodedata.normalize("NFD", "Tài liệu kỹ thuật.pdf")
    pages = [
        {
            "doc_name": nfd_name,
            "page_number": 1,
            "text": "Câu thứ nhất rất quan trọng. Câu thứ hai giải thích định nghĩa chi tiết. Câu thứ ba tổng kết."
        }
    ]
    chunks = chunk_document(pages, chunk_size=50, chunk_overlap=15)
    assert len(chunks) >= 2
    # Ensure doc_name is normalized to NFC
    assert unicodedata.is_normalized("NFC", chunks[0].doc_name)
    # Ensure words are not chopped in half at the beginning of overlapped chunks
    for c in chunks:
        assert not c.text.startswith(" ")
        assert not c.text.endswith(" ")


class _WhitespaceTokenizer:
    """Minimal tokenizer implementing the HuggingFace encode/decode interface."""

    def encode(self, text, add_special_tokens=False):
        return text.split()

    def decode(self, token_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False):
        return " ".join(token_ids)


def test_token_chunking_respects_limit_and_metadata():
    text = " ".join(f"tu{i}" for i in range(120))
    pages = [
        {
            "doc_name": "manual.pdf",
            "page_number": 3,
            "text": text,
        }
    ]

    chunks = chunk_document(
        pages,
        tokenizer=_WhitespaceTokenizer(),
        max_tokens=20,
        overlap_tokens=5,
    )

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.page_number == 3
        assert chunk.doc_name == "manual.pdf"
        assert chunk.metadata["chunk_method"] == "token"
        assert chunk.metadata["token_count"] <= 20
        assert not chunk.text.startswith(" ")
        assert not chunk.text.endswith(" ")


def test_character_chunking_remains_default_without_tokenizer():
    pages = [{"doc_name": "manual.pdf", "page_number": 1, "text": "Câu ngắn. " * 20}]
    chunks = chunk_document(pages, chunk_size=50, chunk_overlap=10)
    assert chunks
    assert all(chunk.metadata["chunk_method"] == "char" for chunk in chunks)

