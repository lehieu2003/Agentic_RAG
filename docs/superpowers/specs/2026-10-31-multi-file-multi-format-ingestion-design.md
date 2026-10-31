# Design Spec: Multi-File & Multi-Format Ingestion Pipeline

- **Date:** 2026-10-31
- **Status:** Draft / Proposed
- **Topic:** Support Multi-File Upload and Multiple Formats (`.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, `.jpeg`)

---

## 1. Overview & Intent

Currently, the Document Q&A Assistant only supports uploading a single `.pdf` file at a time. In real-world technical maintenance and engineering contexts, documentation exists in multiple file formats:
- **PDF manuals** (`.pdf`)
- **Word specifications & reports** (`.docx`)
- **Plain text notes & logs** (`.txt`)
- **Circuit diagrams, schematics & nameplate photos** (`.png`, `.jpg`, `.jpeg`)

This feature enables:
1. **Multi-file Batch Ingestion:** Users can drag & drop multiple files simultaneously in the Streamlit UI, with real-time per-file status updates and summary metrics.
2. **Multi-format Support:** Seamless extraction of text and OCR across `.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, `.jpeg` while preserving document provenance and 1-indexed page metadata for citations.

---

## 2. Architecture & File Structure

```
src/
├── ingestion/
│   ├── document_extractor.py    # NEW: Unified extractor router for all file formats
│   ├── pdf_extractor.py         # Existing: PyMuPDF + RapidOCR for PDFs
│   ├── ocr_engine.py            # Existing: RapidOCR wrapper
│   └── chunker.py               # Existing: Text chunker preserving page numbers
├── api/
│   └── routes.py                # Updated: /upload accepts multi-format documents
└── ui/
    └── components/
        └── sidebar.py           # Updated: Multi-file uploader with batch progress
pyproject.toml                   # Updated: Add python-docx>=1.1.0 dependency
tests/
├── test_document_extractor.py   # NEW: Unit tests for docx, txt, image, and router
├── test_api.py                  # Updated: Test /upload with txt, docx, image
└── test_ui_components.py        # Updated: Test multi-file sidebar upload
```

---

## 3. Extractor Specifications (`src/ingestion/document_extractor.py`)

### 3.1 Unified Interface
All document extractors return a standard list of page dictionaries compatible with `chunk_document`:
```python
List[Dict[str, Any]] = [
    {
        "doc_name": str,
        "page_number": int,       # 1-indexed
        "text": str,
        "is_scanned": bool,
        "image_bytes": bytes | None,
        "error": str | None
    }
]
```

### 3.2 Format Handlers
1. **PDF (`.pdf`):**
   - Delegated to existing `extract_pages_from_pdf`.
   - Uses PyMuPDF with per-page OCR fallback when character count $< 50$.
2. **Word Documents (`.docx`):**
   - Parsed using `python-docx` (`docx.Document(path)`).
   - Extracts all paragraphs and table cell contents.
   - Divides into logical pages of approximately 2,000 characters (page 1, 2, ...) to provide meaningful citation granularity.
   - `is_scanned = False`.
3. **Plain Text (`.txt`):**
   - Decoded with UTF-8 (fallback to `latin-1` or `cp1252` on decoding errors).
   - Divided into logical pages of approximately 2,000 characters.
   - `is_scanned = False`.
4. **Images (`.png`, `.jpg`, `.jpeg`):**
   - Read image bytes directly.
   - Passed to `OcrEngine.extract_text_from_image(image_bytes)`.
   - Represents a single page (`page_number = 1`, `is_scanned = True`).

### 3.3 Router Function
```python
def extract_pages_from_document(
    file_path: str,
    ocr_engine: Optional[Any] = None,
    min_char_threshold: int = 50,
    logical_page_size: int = 2000
) -> List[Dict[str, Any]]:
    ...
```

---

## 4. API Layer Updates (`src/api/routes.py`)

- **Supported Extensions:** `.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, `.jpeg`.
- **Validation:** If the uploaded file extension is not in the supported list, returns `HTTP 400 Bad Request` with detail:
  `"Unsupported file format. Supported formats: .pdf, .docx, .txt, .png, .jpg, .jpeg"`
- **Execution:** Calls `extract_pages_from_document(tmp_path, ocr_engine=ocr_engine)`.
- **Response Schema:**
  ```json
  {
    "filename": "diagram.png",
    "pages_extracted": 1,
    "pages_digital": 0,
    "pages_scanned_ocr": 1,
    "chunks_indexed": 2,
    "status": "success"
  }
  ```

---

## 5. UI Layer Updates (`src/ui/components/sidebar.py`)

- **Multi-File Selection:**
  ```python
  uploaded_files = st.file_uploader(
      "Tải lên tài liệu kỹ thuật",
      type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
      accept_multiple_files=True,
      key="multi_file_uploader",
      help="Hỗ trợ PDF, Word (.docx), Văn bản (.txt) và Ảnh (.png, .jpg)."
  )
  ```
- **Sequential Ingestion Loop:**
  - When user clicks `"🚀 Nạp vào hệ thống"`:
  - Iterates over each file in `uploaded_files`.
  - Displays dynamic per-file status:
    `[i/N] Đang xử lý <filename>...`
  - Aggregates total pages extracted and total chunks indexed across all uploaded files.
  - Fault tolerance: If one file fails (e.g. corrupt format), logs error and continues with remaining files.

---

## 6. Testing Strategy

1. **Unit Testing (`tests/test_document_extractor.py`):**
   - Test `.txt` file extraction with single and multiple logical pages.
   - Test `.docx` file extraction (generated using `python-docx` in temporary test fixtures).
   - Test `.png`/`.jpg` image extraction (generated using `Pillow` with mock/real OCR).
   - Test unsupported extension raises ValueError.
2. **API Endpoint Testing (`tests/test_api.py`):**
   - Test `/upload` with a valid `.txt` file.
   - Test `/upload` with an image file (`.png`).
   - Test `/upload` with unsupported extension (`.exe`, `.csv`) returns 400.
3. **UI Component Testing (`tests/test_ui_components.py`):**
   - Test sidebar multi-file upload flow with mock `ApiClient`.
4. **Regression Testing:**
   - Verify all existing 42 tests continue to pass.
