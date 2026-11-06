from pathlib import Path
from unittest.mock import patch, MagicMock

import docx
import pytest
from PIL import Image

from src.ingestion.document_extractor import extract_pages_from_document
from src.ingestion.ocr_engine import OcrEngine


def test_extract_txt_single_page(tmp_path: Path):
    txt_file = tmp_path / "sample.txt"
    content = "Hello, this is a short test document."
    txt_file.write_text(content, encoding="utf-8")

    pages = extract_pages_from_document(str(txt_file))

    assert len(pages) == 1
    assert pages[0]["doc_name"] == "sample.txt"
    assert pages[0]["page_number"] == 1
    assert pages[0]["text"] == content
    assert pages[0]["is_scanned"] is False
    assert pages[0]["image_bytes"] is None
    assert pages[0]["error"] is None


def test_extract_txt_multiple_logical_pages(tmp_path: Path):
    txt_file = tmp_path / "long_doc.txt"
    # Create 5000 chars of text
    content = ("Page content line with some words.\n" * 150)[:5000]
    txt_file.write_text(content, encoding="utf-8")

    pages = extract_pages_from_document(str(txt_file), logical_page_size=2000)

    assert len(pages) == 3
    for i, page in enumerate(pages):
        assert page["doc_name"] == "long_doc.txt"
        assert page["page_number"] == i + 1
        assert page["is_scanned"] is False
        assert page["image_bytes"] is None
        assert page["error"] is None
        assert len(page["text"]) > 0


def test_extract_docx(tmp_path: Path):
    docx_file = tmp_path / "sample.docx"
    doc = docx.Document()
    doc.add_paragraph("First paragraph about system architecture.")
    doc.add_paragraph("Second paragraph describing components.")

    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Header 1"
    table.cell(0, 1).text = "Header 2"
    table.cell(1, 0).text = "Val A"
    table.cell(1, 1).text = "Val B"

    doc.save(str(docx_file))

    pages = extract_pages_from_document(str(docx_file))

    assert len(pages) == 1
    assert pages[0]["doc_name"] == "sample.docx"
    assert pages[0]["page_number"] == 1
    assert "First paragraph about system architecture." in pages[0]["text"]
    assert "Second paragraph describing components." in pages[0]["text"]
    assert "Header 1" in pages[0]["text"]
    assert "Val A" in pages[0]["text"]
    assert pages[0]["is_scanned"] is False
    assert pages[0]["image_bytes"] is None
    assert pages[0]["error"] is None


def test_extract_image_with_ocr(tmp_path: Path):
    image_file = tmp_path / "diagram.png"
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    img.save(str(image_file), format="PNG")

    with patch.object(OcrEngine, "extract_text_from_image", return_value="EXTRACTED OCR TEXT"):
        pages = extract_pages_from_document(str(image_file))

    assert len(pages) == 1
    assert pages[0]["doc_name"] == "diagram.png"
    assert pages[0]["page_number"] == 1
    assert pages[0]["text"] == "EXTRACTED OCR TEXT"
    assert pages[0]["is_scanned"] is True
    assert pages[0]["image_bytes"] is not None
    assert pages[0]["error"] is None


def test_extract_unsupported_format_raises_value_error(tmp_path: Path):
    unsupported_file = tmp_path / "document.unsupported"
    unsupported_file.write_text("Some text", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file format"):
        extract_pages_from_document(str(unsupported_file))


def test_extract_file_not_found():
    with pytest.raises(FileNotFoundError):
        extract_pages_from_document("non_existent_file_path.pdf")


def test_extract_empty_files(tmp_path: Path):
    # Empty txt
    empty_txt = tmp_path / "empty.txt"
    empty_txt.write_text("", encoding="utf-8")
    txt_pages = extract_pages_from_document(str(empty_txt))
    assert len(txt_pages) == 1
    assert txt_pages[0]["page_number"] == 1
    assert txt_pages[0]["text"] == ""

    # Empty docx
    empty_docx = tmp_path / "empty.docx"
    doc = docx.Document()
    doc.save(str(empty_docx))
    docx_pages = extract_pages_from_document(str(empty_docx))
    assert len(docx_pages) == 1
    assert docx_pages[0]["page_number"] == 1
    assert docx_pages[0]["text"] == ""


def test_extract_pdf_delegates_to_pdf_extractor(tmp_path: Path):
    import pymupdf

    pdf_file = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "Sample text from PDF document for testing delegation to pdf extractor with sufficient length."
    )
    doc.save(str(pdf_file))
    doc.close()

    pages = extract_pages_from_document(str(pdf_file))
    assert len(pages) == 1
    assert pages[0]["doc_name"] == "sample.pdf"
    assert pages[0]["page_number"] == 1
    assert "Sample text from PDF document" in pages[0]["text"]
    assert pages[0]["is_scanned"] is False


def test_extract_jpg_and_jpeg(tmp_path: Path):
    jpg_file = tmp_path / "photo.jpg"
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    img.save(str(jpg_file), format="JPEG")

    mock_engine = MagicMock()
    mock_engine.extract_text_from_image.return_value = "JPG OCR CONTENT"

    pages = extract_pages_from_document(str(jpg_file), ocr_engine=mock_engine)
    assert len(pages) == 1
    assert pages[0]["doc_name"] == "photo.jpg"
    assert pages[0]["page_number"] == 1
    assert pages[0]["text"] == "JPG OCR CONTENT"
    assert pages[0]["is_scanned"] is True
    assert pages[0]["image_bytes"] is not None


def test_extract_txt_non_utf8_fallback(tmp_path: Path):
    latin1_file = tmp_path / "latin1.txt"
    # Write bytes that are valid Latin-1 but invalid UTF-8 (e.g. 0xe9 is é in latin-1)
    latin1_file.write_bytes("Caf\xe9 au lait".encode("latin-1"))

    pages = extract_pages_from_document(str(latin1_file))
    assert len(pages) == 1
    assert "Caf" in pages[0]["text"]

