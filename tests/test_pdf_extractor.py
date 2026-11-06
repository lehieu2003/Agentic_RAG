# tests/test_pdf_extractor.py
import pymupdf
import pytest
from pathlib import Path
from src.ingestion.pdf_extractor import extract_pages_from_pdf

@pytest.fixture
def sample_digital_pdf(tmp_path: Path):
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((50, 72), "Tai lieu ky thuat may bom cong nghiep. Trang 1 gioi thieu.")
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Huong dan bao tri dinh ky van xa va canh bom. Trang 2.")
    file_path = tmp_path / "sample_pump.pdf"
    doc.save(str(file_path))
    doc.close()
    return str(file_path)

def test_extract_pages_from_digital_pdf(sample_digital_pdf):
    pages = extract_pages_from_pdf(sample_digital_pdf)
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "may bom cong nghiep" in pages[0]["text"]
    assert pages[0]["is_scanned"] is False
    assert pages[1]["page_number"] == 2
    assert "bao tri dinh ky" in pages[1]["text"]

def test_extract_pages_per_page_fault_tolerance(sample_digital_pdf, monkeypatch):
    # Review Focus #2: An error processing one page must not crash the entire document
    original_get_text = pymupdf.Page.get_text

    call_count = [0]
    def faulty_get_text(self, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("Corrupted page 1 stream")
        return original_get_text(self, *args, **kwargs)

    monkeypatch.setattr(pymupdf.Page, "get_text", faulty_get_text)

    pages = extract_pages_from_pdf(sample_digital_pdf)
    # Page 1 had error but Page 2 was successfully extracted
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert pages[0]["error"] is not None  # Recorded page error
    assert pages[1]["page_number"] == 2
    assert "bao tri dinh ky" in pages[1]["text"]
