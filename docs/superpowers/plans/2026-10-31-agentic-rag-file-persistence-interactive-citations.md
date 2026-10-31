# Agentic RAG with Persistent Storage & Interactive In-Browser Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Document Q&A Assistant into an autonomous Agentic RAG system that persists uploaded files in `data/uploads/`, prevents duplicate indexing by filename, serves files with in-browser page jumping via `GET /api/v1/files/{filename}#page={N}`, and performs multi-query expansion and corrective retrieval.

**Architecture:**
- `src/config.py`: Add `upload_dir = "data/uploads"`.
- `src/models.py`: Update `UploadResponse` with `status` and `message`; add `FileSummary`; update `QAResponse`.
- `src/api/routes.py`: Implement persistent saving, deduplication by filename, `GET /api/v1/files/{filename}`, `GET /api/v1/files`, and integrate Agentic RAG in `/query`.
- `src/rag/agent.py`: Implement `AgenticRAG` with query expansion, multi-query retrieval, reciprocal deduplication, self-reflection, and corrective re-querying.
- `src/ui/components/chat.py` & `src/ui/styles.py`: Render citation badges as interactive clickable HTML links (`target="_blank"`) pointing to `/api/v1/files/{doc_name}#page={page}`.
- `src/ui/components/sidebar.py`: Display list of ingested files and handle `already_exists` status during batch upload.

---

### Task 1: Persistent File Storage, Deduplication & In-Browser Serving

**Files:**
- Modify: `src/config.py`
- Modify: `src/models.py`
- Modify: `src/api/routes.py`
- Create: `tests/test_file_storage.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- `GET /api/v1/files/{filename}` -> `FileResponse(media_type=..., headers={"Content-Disposition": 'inline; filename="..."'})`
- `GET /api/v1/files` -> `List[FileSummary]`
- `POST /api/v1/upload` -> returns `status="already_exists"` if file exists in `settings.upload_dir`, without re-chunking or re-indexing in Qdrant.

- [ ] **Step 1: Write failing tests for file storage, deduplication, and file serving**
  In `tests/test_file_storage.py`:
  - `test_upload_persists_raw_file(client, tmp_path)`: Verify file is written to `data/uploads/{filename}`.
  - `test_upload_duplicate_file_skips_indexing(client)`: Upload file once (status `success`), upload same file again (status `already_exists`, chunks_indexed=0).
  - `test_serve_file_success(client)`: Upload file, request `GET /api/v1/files/{filename}`, verify status 200, Content-Type, Content-Disposition contains `inline`.
  - `test_serve_file_path_traversal_rejected(client)`: Request `GET /api/v1/files/..%2F..%2Fetc%2Fpasswd` or `../../test.txt`, assert 404.
  - `test_list_files_endpoint(client)`: Verify `GET /api/v1/files` returns uploaded files list with sizes and types.

- [ ] **Step 2: Run tests to verify they fail**
  Run: `.venv/bin/pytest tests/test_file_storage.py -v`
  Expected: FAIL (endpoints not found or logic not implemented).

- [ ] **Step 3: Update `src/config.py` and `src/models.py`**
  - Add `upload_dir: str = "data/uploads"` in `Settings`.
  - Update `UploadResponse` in `src/models.py` with `status: str = "success"` and `message: Optional[str] = None`.
  - Add `FileSummary` model: `filename: str`, `size_bytes: int`, `uploaded_at: str`, `file_type: str`.

- [ ] **Step 4: Update `src/api/routes.py`**
  - Ensure `Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)`.
  - In `upload_document`:
    - Normalize `safe_filename = Path(file.filename).name if file.filename else "uploaded_document"`.
    - Check if `target_path = Path(settings.upload_dir) / safe_filename` exists.
    - If exists, return `UploadResponse(filename=safe_filename, pages_extracted=0, pages_digital=0, pages_scanned_ocr=0, chunks_indexed=0, status="already_exists", message=f"Tài liệu '{safe_filename}' đã tồn tại trên hệ thống. Bỏ qua nạp trùng lặp.")`.
    - If new: write bytes permanently to `target_path`. Then run `extract_pages_from_document(str(target_path))`, chunk, and index into Qdrant.
  - Implement `GET /api/v1/files/{filename}`:
    - Path traversal protection via `safe_name = Path(filename).name`.
    - If not exists: 404 Not Found.
    - Return `FileResponse` with media type and `Content-Disposition: inline; filename="{safe_name}"`.
  - Implement `GET /api/v1/files`:
    - List files in `settings.upload_dir`, returning `List[FileSummary]`.

- [ ] **Step 5: Run tests to verify they pass**
  Run: `.venv/bin/pytest tests/test_file_storage.py tests/test_api.py -v`
  Expected: PASS.

- [ ] **Step 6: Commit Task 1**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/config.py src/models.py src/api/routes.py tests/test_file_storage.py tests/test_api.py
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(api): add persistent file storage, deduplication, and in-browser file serving"
  ```

---

### Task 2: Agentic RAG Engine (Query Expansion, Multi-Query Retrieval & Self-Correction)

**Files:**
- Create: `src/rag/agent.py`
- Modify: `src/models.py`
- Modify: `src/api/routes.py`
- Create: `tests/test_agentic_rag.py`

**Interfaces:**
- Class `AgenticRAG(retriever, llm_client, min_relevance_score=0.45, max_retries=1)`
- Method `answer(question: str) -> QAResponse`

- [ ] **Step 1: Write failing tests for `AgenticRAG`**
  In `tests/test_agentic_rag.py`:
  - `test_agent_query_expansion_generates_variations`: Test `expand_query("áp suất máy bơm")` returns list of 1-3 distinct formulations.
  - `test_agent_multi_query_retrieval_deduplication`: Mock retriever with overlapping chunks for 2 queries, verify chunks are merged and deduplicated by chunk identifier.
  - `test_agent_self_reflection_triggers_query_rewrite_on_low_score`: Mock retriever returning score < 0.45 on first query, verify `rewrite_query` is invoked and second search is executed.
  - `test_agent_citation_grounding_preserves_valid_and_rejects_hallucinations`: Verify that synthesized answer citations are strictly verified against retrieved chunks.
  - `test_agent_abstains_when_no_relevant_data_found`: Test question with zero relevant chunks yields `abstained=True`.

- [ ] **Step 2: Run tests to verify they fail**
  Run: `.venv/bin/pytest tests/test_agentic_rag.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'src.rag.agent'`.

- [ ] **Step 3: Implement `src/rag/agent.py`**
  - Implement `AgenticRAG`:
    - `expand_query(question: str) -> List[str]`:
      If LLM client is available, prompt LLM to output 1-3 concise technical search variations (comma/newline separated). In mock mode, generate standard variations `[question, f"{question} thông số kỹ thuật"]`.
    - `multi_query_retrieve(queries: List[str], top_k: int = 5) -> List[RetrievalResult]`:
      Query retriever for each variation. Merge results, keep highest score per `(doc_name, page_number, chunk_index)`. Sort by score descending.
    - `rewrite_query(question: str, attempted_queries: List[str]) -> str`:
      Generate an alternative search formulation with broader synonyms.
    - `answer(question: str) -> QAResponse`:
      1. Expand original query into variations.
      2. Multi-query retrieve candidates.
      3. Check max score: if < `min_relevance_score` and retry count < 1:
         - Generate rewritten query.
         - Retrieve additional chunks and merge.
      4. If still no chunks >= `min_relevance_score`: return `QAResponse(answer=ABSTAIN_PHRASE, citations=[], abstained=True)`.
      5. Synthesize answer with citations using LLM or mock generator.
      6. Parse and verify citations against retrieved chunks. Return structured `QAResponse`.
  - Update `QAResponse` in `src/models.py` to optionally include `rewritten_queries: Optional[List[str]] = None` and `reasoning_steps: Optional[List[str]] = None`.

- [ ] **Step 4: Wire `AgenticRAG` into `src/api/routes.py`**
  - In `src/api/routes.py`, initialize `AgenticRAG(retriever=retriever, llm_client=llm_client, min_relevance_score=settings.min_relevance_score)`.
  - Use `agent.answer(request.question)` in `POST /api/v1/query`.

- [ ] **Step 5: Run tests to verify they pass**
  Run: `.venv/bin/pytest tests/test_agentic_rag.py tests/test_api.py -v`
  Expected: PASS.

- [ ] **Step 6: Commit Task 2**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/rag/agent.py src/models.py src/api/routes.py tests/test_agentic_rag.py
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(rag): implement AgenticRAG with query expansion and corrective retrieval"
  ```

---

### Task 3: Interactive Clickable Citations & Document Viewer UI

**Files:**
- Modify: `src/ui/components/chat.py`
- Modify: `src/ui/styles.py`
- Modify: `src/ui/components/sidebar.py`
- Modify: `src/ui/api_client.py`
- Modify: `tests/test_ui_components.py`

**Interfaces:**
- `format_citation_badge(doc_name: str, page: int, api_base_url: str) -> str` returns clickable HTML anchor.
- Sidebar displays ingested documents and marks already-existing files without throwing errors.

- [ ] **Step 1: Write failing tests for interactive citations and UI updates**
  In `tests/test_ui_components.py`:
  - `test_format_citation_badge_renders_clickable_html_link`: Verify badge includes `<a href=".../api/v1/files/{doc_name}#page={page}" target="_blank"`.
  - `test_render_sidebar_handles_already_exists_status`: Mock API returning `status="already_exists"`, assert UI displays info message `"Đã tồn tại"` instead of error.

- [ ] **Step 2: Run tests to verify they fail**
  Run: `.venv/bin/pytest tests/test_ui_components.py -k "test_format_citation_badge_renders_clickable_html_link" -v`
  Expected: FAIL.

- [ ] **Step 3: Update `src/ui/components/chat.py` and `src/ui/styles.py`**
  - In `chat.py`:
    - `format_citation_badge(doc_name: str, page: int, api_base_url: str = "http://localhost:8000") -> str`:
      Returns clickable badge `<a href="{api_base_url}/api/v1/files/{doc_name}#page={page}" target="_blank" class="citation-badge" title="Mở {doc_name} tại trang {page}">📄 {doc_name} (Trang {page}) ↗</a>`.
    - In `render_evidence_expander`: Add a direct link button `"🔗 Xem trang gốc trong trình duyệt"` for each citation chunk.
  - In `styles.py`: Add CSS styles for `.citation-badge` with hover transition, underline on hover, and pointer cursor.

- [ ] **Step 4: Update `src/ui/components/sidebar.py` and `src/ui/api_client.py`**
  - Add `list_files()` method in `ApiClient` calling `GET /api/v1/files`.
  - In `sidebar.py`:
    - Render an expander `"📚 Tài liệu đã nạp trên hệ thống"` showing list of stored files and sizes.
    - In batch upload loop: If API response has `status == "already_exists"`, show `st.info(f"ℹ️ {file.name}: {res.get('message', 'Đã tồn tại')}")` and count as existing, preserving `uploaded=True`.

- [ ] **Step 5: Run tests to verify they pass**
  Run: `.venv/bin/pytest tests/test_ui_components.py -v`
  Expected: PASS.

- [ ] **Step 6: Commit Task 3**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/ui/components/chat.py src/ui/styles.py src/ui/components/sidebar.py src/ui/api_client.py tests/test_ui_components.py
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(ui): add interactive clickable citations with in-browser page jumping and file management"
  ```

---

### Task 4: Full Regression Testing & Documentation

**Files:**
- Modify: `README.md`
- Test: Full test suite verification across all modules

- [ ] **Step 1: Run full test suite**
  Run: `.venv/bin/pytest -v`
  Expected: ALL PASS (65+ tests).

- [ ] **Step 2: Update `README.md`**
  - Document persistent file storage in `data/uploads/` and deduplication by filename.
  - Document the interactive clickable citation feature (`/api/v1/files/{filename}#page={page}`).
  - Document the Agentic RAG architecture (query expansion, multi-query retrieval, self-reflection loop).

- [ ] **Step 3: Commit Task 4**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add README.md
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "docs: document agentic RAG loop, persistent storage, and interactive citations"
  ```
