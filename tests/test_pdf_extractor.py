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
