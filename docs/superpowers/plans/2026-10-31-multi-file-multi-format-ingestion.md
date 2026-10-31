# Multi-File & Multi-Format Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Document Q&A Assistant ingestion pipeline to support multi-file batch uploads and multi-format extraction across `.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, and `.jpeg`.

**Architecture:**
- Create `src/ingestion/document_extractor.py` as a unified extraction router.
- `.pdf` files are routed to `extract_pages_from_pdf` (preserving PyMuPDF + OCR fallback).
- `.docx` files are parsed via `python-docx` into logical pages (~2,000 chars/page).
- `.txt` files are decoded and chunked into logical pages (~2,000 chars/page).
- Image files (`.png`, `.jpg`, `.jpeg`) are sent to `OcrEngine.extract_text_from_image` as a single scanned page (`page_number=1`, `is_scanned=True`).
- `/api/v1/upload` in `src/api/routes.py` validates allowed extensions and invokes the unified extractor.
- `src/ui/components/sidebar.py` enables `accept_multiple_files=True` with sequential batch execution, per-file status updates, and aggregated metrics.

---

### Task 1: Project Dependencies & Unified Document Extractor

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ingestion/document_extractor.py`
- Create: `tests/test_document_extractor.py`

**Interfaces:**
- Produces:
  - `src.ingestion.document_extractor.extract_pages_from_document(file_path: str, ocr_engine: Optional[Any] = None, min_char_threshold: int = 50, logical_page_size: int = 2000) -> List[Dict[str, Any]]`
  - Returns `List[Dict[str, Any]]` compatible with `chunk_document`: `[{"doc_name": str, "page_number": int, "text": str, "is_scanned": bool, "image_bytes": bytes | None, "error": str | None}]`

- [ ] **Step 1: Add `python-docx` dependency and install in environment**
  Add `"python-docx>=1.1.0"` to `dependencies` in `pyproject.toml`.
  Run `.venv/bin/pip install "python-docx>=1.1.0"`.

- [ ] **Step 2: Write failing unit tests for `document_extractor`**
  In `tests/test_document_extractor.py`:
  - `test_extract_txt_single_page(tmp_path)`: creates a `.txt` file with short text, checks extracted `doc_name`, `page_number=1`, `is_scanned=False`.
  - `test_extract_txt_multiple_logical_pages(tmp_path)`: creates `.txt` file with 5000 characters, checks that it produces multiple pages with sequential `page_number`s.
  - `test_extract_docx(tmp_path)`: creates `.docx` document using `docx.Document()`, adds paragraphs and table, checks extraction.
  - `test_extract_image_with_ocr(tmp_path)`: creates dummy `.png` using `PIL.Image`, mocks `OcrEngine.extract_text_from_image`, checks `page_number=1` and `is_scanned=True`.
  - `test_extract_unsupported_format_raises_value_error(tmp_path)`: checks `.unsupported` raises `ValueError`.

- [ ] **Step 3: Run tests to verify they fail**
  Run: `.venv/bin/pytest tests/test_document_extractor.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'src.ingestion.document_extractor'`.

- [ ] **Step 4: Implement `src/ingestion/document_extractor.py`**
  Implement:
  - Helper `_extract_txt(path, logical_page_size)` with UTF-8 / fallback encoding and page splitting.
  - Helper `_extract_docx(path, logical_page_size)` with paragraph and table extraction and logical page splitting.
  - Helper `_extract_image(path, ocr_engine)` reading bytes and invoking OCR.
  - Main router `extract_pages_from_document(file_path, ocr_engine=None, ...)` delegating based on file suffix.

- [ ] **Step 5: Run tests to verify they pass**
  Run: `.venv/bin/pytest tests/test_document_extractor.py -v`
  Expected: PASS.

- [ ] **Step 6: Commit Task 1**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add pyproject.toml src/ingestion/document_extractor.py tests/test_document_extractor.py
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: add multi-format document extractor for docx, txt, and images"
  ```

---

### Task 2: API Layer Multi-Format Validation & Ingestion

**Files:**
- Modify: `src/api/routes.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/upload`: accepts `.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, `.jpeg`.
  - Rejects other extensions with HTTP 400.

- [ ] **Step 1: Write failing integration tests for `/upload` with new formats**
  In `tests/test_api.py`:
  - `test_upload_txt_endpoint(client)`: Upload a `.txt` file, assert 200, status `success`, `pages_extracted >= 1`, `chunks_indexed >= 1`.
  - `test_upload_png_endpoint(client)`: Upload a small test `.png`, assert 200, status `success`.
  - `test_upload_unsupported_format_returns_400(client)`: Upload a `.zip` file, assert 400, detail contains `"Unsupported file format"`.

- [ ] **Step 2: Run tests to verify they fail**
  Run: `.venv/bin/pytest tests/test_api.py -k "test_upload_txt_endpoint or test_upload_png_endpoint" -v`
  Expected: FAIL with 400 `"Only PDF documents are supported."`.

- [ ] **Step 3: Update `src/api/routes.py`**
  - Define `SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}`.
  - Validate file extension against `SUPPORTED_EXTENSIONS`.
  - Call `extract_pages_from_document(tmp_path, ocr_engine=ocr_engine)` instead of `extract_pages_from_pdf`.

- [ ] **Step 4: Run tests to verify they pass**
  Run: `.venv/bin/pytest tests/test_api.py -v`
  Expected: PASS.

- [ ] **Step 5: Commit Task 2**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/api/routes.py tests/test_api.py
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(api): allow uploading docx, txt, and images to /upload endpoint"
  ```

---

### Task 3: Streamlit Sidebar Multi-File Batch Ingestion

**Files:**
- Modify: `src/ui/components/sidebar.py`
- Modify: `tests/test_ui_components.py`

**Interfaces:**
- Produces:
  - `render_sidebar(api_client)`:
    - `st.file_uploader(accept_multiple_files=True, type=["pdf", "docx", "txt", "png", "jpg", "jpeg"])`
    - Sequential iteration over uploaded files.
    - Aggregated metrics display: total files, total pages, total chunks.

- [ ] **Step 1: Write test for multi-file sidebar processing**
  In `tests/test_ui_components.py`:
  - Update `test_render_sidebar_upload_process` to pass a list of 2 mock files (`[file1.pdf, file2.docx]`).
  - Assert `api_client.upload_document` is called for both files.
  - Assert returned `res["uploaded"] is True`.

- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_ui_components.py -k test_render_sidebar_upload_process -v`
  Expected: FAIL.

- [ ] **Step 3: Update `src/ui/components/sidebar.py`**
  - Update `st.file_uploader` with `accept_multiple_files=True` and `type=["pdf", "docx", "txt", "png", "jpg", "jpeg"]`.
  - When `"🚀 Nạp vào hệ thống"` is clicked:
    - Iterate over `uploaded_files` with `enumerate(uploaded_files, 1)`.
    - Render per-file progress inside `st.status`.
    - Accumulate `total_pages` and `total_chunks`.
    - Display summary metrics: `Số tệp đã nạp`, `Tổng số trang`, `Tổng số chunks`.
    - Handle per-file exceptions gracefully.

- [ ] **Step 4: Run tests to verify they pass**
  Run: `.venv/bin/pytest tests/test_ui_components.py -v`
  Expected: PASS.

- [ ] **Step 5: Commit Task 3**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/ui/components/sidebar.py tests/test_ui_components.py
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(ui): support multi-file batch upload with progress tracking"
  ```

---

### Task 4: Full Regression Testing & Documentation

**Files:**
- Modify: `README.md`
- Test: Full test suite verification across all modules

- [ ] **Step 1: Run full test suite**
  Run: `.venv/bin/pytest -v`
  Expected: ALL PASS (48+ tests).

- [ ] **Step 2: Update `README.md`**
  Document the supported formats (`.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, `.jpeg`) and the multi-file upload capability in Section 2 (Core Features) and Section 3 (Usage).

- [ ] **Step 3: Commit Task 4**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add README.md
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "docs: document multi-format and multi-file batch upload support"
  ```
