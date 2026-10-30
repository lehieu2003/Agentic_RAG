# Streamlit ChatGPT-style UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng giao diện web tương tác trực quan bằng Streamlit theo phong cách ChatGPT cho hệ thống Document Q&A Assistant, giao tiếp với FastAPI Backend qua REST API.

**Architecture:** Decoupled Client-Server. Lớp UI được đóng gói trong `src/ui/`, sử dụng `httpx` để kết nối tới FastAPI Backend (`http://localhost:8000/api/v1/`). Giao diện gồm Sidebar (quản lý upload PDF, trạng thái backend, top_k slider, nút tạo chat mới) và Main Chat Area (Empty state gợi ý câu hỏi, tin nhắn bong bóng chuẩn ChatGPT, thẻ trích dẫn Citations, cảnh báo Abstention, và Expander xem chi tiết Retrieved Chunks & Scores).

**Tech Stack:** Python 3.12, Streamlit >= 1.32.0, HTTPX, Pydantic v2, Pytest.

**Spec:** [docs/superpowers/specs/2026-10-30-streamlit-ui-design.md](file:///Users/lehieu/Projects/personal/Agentic_RAG/docs/superpowers/specs/2026-10-30-streamlit-ui-design.md)

---

## Global Constraints

- Python version floor: `>= 3.10`.
- Tách biệt hoàn toàn UI và Backend: Streamlit không import trực tiếp database/vector client nội bộ, mọi giao tiếp thực hiện qua `ApiClient` gọi REST API (`/health`, `/upload`, `/query`).
- Định dạng trích dẫn nguồn: Hiển thị badge trực quan `[Tài liệu: <doc_name>, Trang <page_number>]`.
- Cơ chế Abstention: Khi `abstained == True`, hiển thị hộp cảnh báo màu vàng/cam thông minh, không hiển thị trích dẫn rỗng hoặc trích dẫn ảo.
- Quản lý trạng thái: Sử dụng `st.session_state` cho `messages`, `top_k`, `pending_prompt`.

---

## Review Focus

1. **FastAPI Backend Offline:** Khi server FastAPI chưa chạy hoặc bị tắt, UI không được crash màn hình đỏ mà phải hiển thị banner cảnh báo rõ ràng `🔴 Backend Offline` và hướng dẫn người dùng lệnh khởi động.
2. **File upload không phải PDF:** Hệ thống uploader phải chặn ngay từ UI và báo lỗi nếu người dùng tải lên định dạng khác `.pdf`.
3. **Hiển thị Abstention chuẩn xác:** Khi backend trả về `abstained: true`, khung chat hiển thị thông báo từ chối suy đoán chuẩn và ẩn hoặc cảnh báo về các chunk không đủ tin cậy.
4. **Nút gợi ý câu hỏi (Prompt suggestions):** Khi bấm vào câu hỏi mẫu ở màn hình chào đón (Empty state), câu hỏi phải được tự động gửi đi và hiển thị phản hồi ngay lập tức mà không làm mất trạng thái.
5. **Nút "+ New Chat":** Nhấn tạo chat mới phải reset hoàn toàn lịch sử tin nhắn trong `st.session_state` và đưa UI về màn hình gợi ý ban đầu.

---

### Task 1: Project Dependencies & API Client Layer

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ui/__init__.py`
- Create: `src/ui/api_client.py`
- Test: `tests/test_ui_api_client.py`

**Interfaces:**
- Produces:
  - `src.ui.api_client.ApiClient(base_url: str = "http://localhost:8000/api/v1", timeout: float = 60.0)`
    - `check_health() -> dict | None`
    - `upload_document(file_bytes: bytes, filename: str) -> dict`
    - `query(question: str, top_k: int = 3) -> QAResponse`

- [ ] **Step 1: Write the failing tests for ApiClient**

```python
# tests/test_ui_api_client.py
import pytest
from unittest.mock import MagicMock, patch
import httpx
from src.ui.api_client import ApiClient
from src.models import QAResponse, Citation, RetrievalResult, DocumentChunk

def test_check_health_success():
    client = ApiClient(base_url="http://testserver/api/v1")
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = httpx.Response(200, json={"status": "ok", "retrieval_mode": "local"})
        res = client.check_health()
        assert res is not None
        assert res["status"] == "ok"

def test_check_health_connection_error():
    client = ApiClient(base_url="http://testserver/api/v1")
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Failed")):
        res = client.check_health()
        assert res is None

def test_upload_document_success():
    client = ApiClient(base_url="http://testserver/api/v1")
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = httpx.Response(200, json={"filename": "test.pdf", "chunks_indexed": 4, "status": "success"})
        res = client.upload_document(b"%PDF-1.4 dummy", "test.pdf")
        assert res["status"] == "success"
        assert res["chunks_indexed"] == 4

def test_query_success():
    client = ApiClient(base_url="http://testserver/api/v1")
    payload = {
        "answer": "Ap suat bom giam do ro ri van [Tai lieu: pump.pdf, Trang 1].",
        "citations": [{"doc_name": "pump.pdf", "page_number": 1}],
        "abstained": False,
        "retrieved_chunks": []
    }
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = httpx.Response(200, json=payload)
        resp = client.query("Nguyen nhan giam ap suat?", top_k=3)
        assert isinstance(resp, QAResponse)
        assert resp.abstained is False
        assert len(resp.citations) == 1
        assert resp.citations[0].page_number == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ui_api_client.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ui'`

- [ ] **Step 3: Update `pyproject.toml`, install dependencies & implement `ApiClient`**

1. Add `"streamlit>=1.32.0"` to `dependencies` in `pyproject.toml`.
2. Run `.venv/bin/python -m pip install streamlit`.
3. Create `src/ui/__init__.py`.
4. Implement `src/ui/api_client.py` with error handling, timeout configuration, and response parsing.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ui_api_client.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add pyproject.toml src/ui/ tests/test_ui_api_client.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: add streamlit dependency and ApiClient layer"
```

---

### Task 2: UI Chat Components & Source Formatter

**Files:**
- Create: `src/ui/components/__init__.py`
- Create: `src/ui/components/chat.py`
- Test: `tests/test_ui_components.py`

**Interfaces:**
- Produces:
  - `src.ui.components.chat.PROMPT_SUGGESTIONS: list[str]`
  - `src.ui.components.chat.render_citation_badges(citations: list[Citation])`
  - `src.ui.components.chat.render_evidence_expander(chunks: list[RetrievalResult])`
  - `src.ui.components.chat.render_assistant_message(response: QAResponse)`

- [ ] **Step 1: Write the failing tests for chat formatting helpers**

```python
# tests/test_ui_components.py
from src.models import Citation, RetrievalResult, DocumentChunk, QAResponse
from src.ui.components.chat import PROMPT_SUGGESTIONS, format_citation_badge

def test_prompt_suggestions_not_empty():
    assert len(PROMPT_SUGGESTIONS) >= 3
    assert any("áp suất" in p.lower() for p in PROMPT_SUGGESTIONS)

def test_format_citation_badge():
    c = Citation(doc_name="pump_maintenance_guide.pdf", page_number=2)
    badge = format_citation_badge(c)
    assert "pump_maintenance_guide.pdf" in badge
    assert "Trang 2" in badge
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ui_components.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ui.components'`

- [ ] **Step 3: Implement `src/ui/components/chat.py`**

Implement:
1. `PROMPT_SUGGESTIONS`: List of 3 technical questions from sample technical docs.
2. `format_citation_badge(c: Citation) -> str`.
3. `render_citation_badges(citations: list[Citation])`: Display badges using `st.markdown` pills / badges.
4. `render_evidence_expander(chunks: list[RetrievalResult])`: Collapsible expander displaying chunk text, score, and page number.
5. `render_assistant_message(message: dict)`: Renders text, abstention warning banner if `abstained == True`, citations, and evidence expander.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ui_components.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add src/ui/components/ tests/test_ui_components.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: implement chat rendering components and citation badge formatters"
```

---

### Task 3: Sidebar Controls & Document Ingestion Component

**Files:**
- Create: `src/ui/components/sidebar.py`
- Modify: `tests/test_ui_components.py`

**Interfaces:**
- Produces:
  - `src.ui.components.sidebar.render_sidebar(api_client: ApiClient) -> dict`:
    - Returns `{"top_k": int, "reset_chat": bool, "uploaded": bool}`

- [ ] **Step 1: Write test verifying sidebar logic handlers**

```python
# append to tests/test_ui_components.py
def test_sidebar_health_mapping():
    from src.ui.components.sidebar import format_backend_status
    assert "Online" in format_backend_status({"status": "ok", "retrieval_mode": "local"})
    assert "Offline" in format_backend_status(None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ui_components.py -k test_sidebar_health_mapping -v`  
Expected: FAIL with `ImportError: cannot import name 'format_backend_status'`

- [ ] **Step 3: Implement `src/ui/components/sidebar.py`**

Implement:
1. `format_backend_status(health_info: dict | None) -> str`
2. `render_sidebar(api_client: ApiClient) -> dict`:
   - Button `+ New Chat` (sets reset flag).
   - Backend health badge with status dot (🟢 / 🔴).
   - Document upload section: `st.file_uploader(type=["pdf"])`, button "Nạp tài liệu", calls `api_client.upload_document` with progress spinner and status display.
   - Slider `top_k`: 1 to 10 (default: 3).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ui_components.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add src/ui/components/sidebar.py tests/test_ui_components.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: implement sidebar controls and upload ingestion component"
```

---

### Task 4: Main Streamlit Application & State Orchestration

**Files:**
- Create: `src/ui/app.py`
- Create: `tests/test_ui_app.py`

**Interfaces:**
- Produces:
  - `src.ui.app.main()`: Orchestrates session state, sidebar, chat history, prompt suggestions, and query execution.

- [ ] **Step 1: Write smoke test for app initialization**

```python
# tests/test_ui_app.py
import pytest
from src.ui.app import init_session_state

def test_init_session_state():
    mock_state = {}
    init_session_state(mock_state)
    assert "messages" in mock_state
    assert isinstance(mock_state["messages"], list)
    assert "pending_prompt" in mock_state
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ui_app.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ui.app'`

- [ ] **Step 3: Implement `src/ui/app.py`**

Implement:
1. `st.set_page_config(page_title="Document Q&A Assistant", page_icon="🤖", layout="wide")`.
2. `init_session_state(state)`: Initializes `messages`, `pending_prompt`, `top_k`.
3. Sidebar rendering via `render_sidebar(api_client)`.
4. Empty state: Render header and prompt suggestion buttons if `len(messages) == 0`.
5. Message history loop: Render each message using `render_assistant_message` / user message.
6. Chat input handler:
   - Captures user input or clicked suggestion.
   - Calls `api_client.query(prompt, top_k=top_k)`.
   - Appends to session state and calls `st.rerun()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ui_app.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add src/ui/app.py tests/test_ui_app.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: complete Streamlit ChatGPT-style application"
```

---

### Task 5: End-to-End Verification & Documentation

**Files:**
- Modify: `README.md`
- Test: Full test suite verification across all components

- [ ] **Step 1: Run full test suite to verify 0 regressions**

Run: `.venv/bin/pytest -v`  
Expected: ALL PASS (existing 26+ tests + new UI tests)

- [ ] **Step 2: Update `README.md`**

Add instructions for running the Streamlit UI:
```bash
# Khởi động Backend
.venv/bin/uvicorn src.api.main:app --port 8000 --reload

# Khởi động Streamlit UI
.venv/bin/streamlit run src/ui/app.py
```
Include screenshot description and feature overview.

- [ ] **Step 3: Commit and verify clean status**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add README.md
GIT_CONFIG_GLOBAL=/dev/null git commit -m "docs: add Streamlit UI running instructions to README"
```
