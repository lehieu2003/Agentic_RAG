"""PDF text extraction using PyMuPDF with page metadata tracking and fault tolerance."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import pymupdf


def extract_pages_from_pdf(
    pdf_path: str,
    ocr_engine: Optional[Any] = None,
    min_char_threshold: int = 50
) -> List[Dict[str, Any]]:
    """Extract text from each page of a PDF document, preserving page numbers.

    Each page is extracted independently with fault tolerance: an error on one page
    (e.g., rendering issue) does not interrupt extraction of other pages.

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
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    doc_name = path.name
    results: List[Dict[str, Any]] = []

    doc = pymupdf.open(str(path))
    try:
        for page_idx in range(len(doc)):
            page_number = page_idx + 1
            try:
                page = doc[page_idx]
                raw_text = page.get_text().strip()

                if len(raw_text) < min_char_threshold:
                    # Scanned or image-heavy page: render to high-res pixmap
                    pix = page.get_pixmap(dpi=300)
                    image_bytes = pix.tobytes("png")
                    is_scanned = True

                    extracted_text = raw_text
                    if ocr_engine is not None and hasattr(ocr_engine, "extract_text_from_image"):
                        ocr_text = ocr_engine.extract_text_from_image(image_bytes)
                        if ocr_text:
                            extracted_text = (raw_text + "\n" + ocr_text).strip() if raw_text else ocr_text.strip()
                else:
                    image_bytes = None
                    is_scanned = False
                    extracted_text = raw_text

                results.append({
                    "doc_name": doc_name,
                    "page_number": page_number,
                    "text": extracted_text,
                    "is_scanned": is_scanned,
                    "image_bytes": image_bytes,
                    "error": None
                })
            except Exception as e:
                # Per-page fault tolerance: record page error and continue with next pages
                results.append({
                    "doc_name": doc_name,
                    "page_number": page_number,
                    "text": "",
                    "is_scanned": False,
                    "image_bytes": None,
                    "error": str(e)
                })
    finally:
        doc.close()

    return results
