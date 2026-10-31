"""Unified document text extraction supporting PDF, DOCX, TXT, and images."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import unicodedata
import docx

from src.ingestion.pdf_extractor import extract_pages_from_pdf
from src.ingestion.ocr_engine import OcrEngine


def _segment_text(text: str, logical_page_size: int = 2000) -> List[str]:
    """Segment a string of text into logical pages of ~logical_page_size characters."""
    text = text.strip()
    if not text:
        return [""]

    if len(text) <= logical_page_size:
        return [text]

    pages: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + logical_page_size, text_len)
        if end < text_len:
            # Look for natural split near the boundary (in last 20% of slice)
            search_start = start + int(logical_page_size * 0.8)
            breakpoint = -1
            for sep in ["\n\n", "\n", ". ", " "]:
                pos = text.rfind(sep, search_start, end)
                if pos != -1:
                    breakpoint = pos + len(sep)
                    break
            if breakpoint != -1:
                end = breakpoint

        page_str = text[start:end].strip()
        if page_str:
            pages.append(page_str)
        start = end

    return pages if pages else [""]


def _extract_txt(path: Path, logical_page_size: int = 2000) -> List[Dict[str, Any]]:
    """Extract text from plain text file with logical page segmentation."""
    doc_name = unicodedata.normalize("NFC", path.name)
    try:
        try:
            full_text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                full_text = path.read_text(encoding="latin-1")
            except Exception:
                full_text = path.read_text(encoding="utf-8", errors="ignore")

        segments = _segment_text(full_text, logical_page_size)
        return [
            {
                "doc_name": doc_name,
                "page_number": idx + 1,
                "text": seg,
                "is_scanned": False,
                "image_bytes": None,
                "error": None,
            }
            for idx, seg in enumerate(segments)
        ]
    except Exception as e:
        return [
            {
                "doc_name": doc_name,
                "page_number": 1,
                "text": "",
                "is_scanned": False,
                "image_bytes": None,
                "error": str(e),
            }
        ]


def _extract_docx(path: Path, logical_page_size: int = 2000) -> List[Dict[str, Any]]:
    """Extract text from DOCX file including paragraphs and tables."""
    doc_name = unicodedata.normalize("NFC", path.name)
    try:
        doc = docx.Document(str(path))
        text_parts: List[str] = []

        for p in doc.paragraphs:
            p_text = p.text.strip()
            if p_text:
                text_parts.append(p_text)

        for table in doc.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells]
                if any(row_cells):
                    text_parts.append(" | ".join(row_cells))

        full_text = "\n\n".join(text_parts).strip()
        segments = _segment_text(full_text, logical_page_size)

        return [
            {
                "doc_name": doc_name,
                "page_number": idx + 1,
                "text": seg,
                "is_scanned": False,
                "image_bytes": None,
                "error": None,
            }
            for idx, seg in enumerate(segments)
        ]
    except Exception as e:
        return [
            {
                "doc_name": doc_name,
                "page_number": 1,
                "text": "",
                "is_scanned": False,
                "image_bytes": None,
                "error": str(e),
            }
        ]


def _extract_image(
    path: Path,
    ocr_engine: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Extract text from image file using OCR."""
    doc_name = unicodedata.normalize("NFC", path.name)
    try:
        image_bytes = path.read_bytes()
        extracted_text = ""

        active_ocr_engine = ocr_engine
        if active_ocr_engine is None:
            try:
                active_ocr_engine = OcrEngine()
            except Exception:
                active_ocr_engine = None

        if active_ocr_engine is not None and hasattr(active_ocr_engine, "extract_text_from_image"):
            extracted = active_ocr_engine.extract_text_from_image(image_bytes)
            if extracted:
                extracted_text = extracted.strip()

        return [
            {
                "doc_name": doc_name,
                "page_number": 1,
                "text": extracted_text,
                "is_scanned": True,
                "image_bytes": image_bytes,
                "error": None,
            }
        ]
    except Exception as e:
        return [
            {
                "doc_name": doc_name,
                "page_number": 1,
                "text": "",
                "is_scanned": True,
                "image_bytes": None,
                "error": str(e),
            }
        ]


def extract_pages_from_document(
    file_path: str,
    ocr_engine: Optional[Any] = None,
    min_char_threshold: int = 50,
    logical_page_size: int = 2000,
) -> List[Dict[str, Any]]:
    """Extract text from document supporting PDF, DOCX, TXT, and image formats.

    Args:
        file_path: Path to the target file.
        ocr_engine: Optional OCR engine instance for scanned/image extraction.
        min_char_threshold: Character count below which a PDF page is treated as scanned.
        logical_page_size: Approximate character limit for segmenting TXT and DOCX files.

    Returns:
        List of dicts: [
            {
                "doc_name": str,
                "page_number": int,  # 1-indexed
                "text": str,
                "is_scanned": bool,
                "image_bytes": bytes | None,
                "error": str | None
            }
        ]
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()

    if ext == ".pdf":
        return extract_pages_from_pdf(
            pdf_path=str(path),
            ocr_engine=ocr_engine,
            min_char_threshold=min_char_threshold,
        )
    elif ext == ".docx":
        return _extract_docx(path=path, logical_page_size=logical_page_size)
    elif ext == ".txt":
        return _extract_txt(path=path, logical_page_size=logical_page_size)
    elif ext in {".png", ".jpg", ".jpeg"}:
        return _extract_image(path=path, ocr_engine=ocr_engine)
    else:
        raise ValueError(f"Unsupported file format: {ext}")
