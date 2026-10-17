# tests/test_ocr_engine.py
import pytest
from PIL import Image, ImageDraw
import io
import pymupdf
from pathlib import Path
from src.ingestion.ocr_engine import OcrEngine
from src.ingestion.pdf_extractor import extract_pages_from_pdf

@pytest.fixture
def sample_scanned_image_bytes():
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 35), "CANH BAO AP SUAT CAO", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def test_ocr_extract_text(sample_scanned_image_bytes):
    engine = OcrEngine()
    text = engine.extract_text_from_image(sample_scanned_image_bytes)
    assert "AP SUAT" in text.upper() or "CANH BAO" in text.upper()

def test_extract_pages_with_ocr_fallback(tmp_path: Path, sample_scanned_image_bytes):
    # Create PDF with an image page (scanned page without digital text)
    doc = pymupdf.open()
    page = doc.new_page()
    rect = pymupdf.Rect(50, 50, 450, 150)
    page.insert_image(rect, stream=sample_scanned_image_bytes)
    pdf_file = tmp_path / "scanned_doc.pdf"
    doc.save(str(pdf_file))
    doc.close()

    engine = OcrEngine()
    pages = extract_pages_from_pdf(str(pdf_file), ocr_engine=engine)
    assert len(pages) == 1
    assert pages[0]["is_scanned"] is True
    assert "AP SUAT" in pages[0]["text"].upper() or "CANH BAO" in pages[0]["text"].upper()
