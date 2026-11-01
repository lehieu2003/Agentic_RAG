# Multi-Turn Conversation Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement persistent multi-turn conversation memory (SQLite session store) and history-aware query contextualization (standalone query rewriting) in the LangGraph agent, FastAPI REST API, and React SPA frontend.

**Architecture:** Python standard library `sqlite3` persists sessions and message history in `data/chat_history.db`. A new `0_contextualize_query` node in LangGraph uses LLM to resolve pronouns and relative references into standalone queries before retrieval. The FastAPI `/api/v1/query` endpoint accepts optional `session_id` (auto-creating one if absent), and returns `session_id` and `standalone_question`. The React SPA sidebar displays recent chat sessions with instant thread switching and deletion.

**Tech Stack:** Python 3.12, SQLite (`sqlite3`), LangGraph, FastAPI, Pydantic, React 19, TypeScript, Tailwind CSS, Vitest, Pytest.

**Spec:** `docs/superpowers/specs/2026-11-01-multi-turn-conversation-context-design.md`

## Global Constraints

- **Zero Breaking Changes:** Calling `POST /api/v1/query` without `session_id` must auto-create a session and return 200 without breaking any existing backend API caller or the 112 existing pytest tests.
- **Zero External DB Dependencies:** Use Python standard library `sqlite3` exclusively for session storage at `data/chat_history.db`.
- **Sliding Window Cap:** Limit conversation context sent to LLM prompts to the last 10 messages (5 exchange pairs) to prevent prompt dilution and token overflow.
- **URL Encoding:** Always use `encodeURIComponent` when building session deletion and retrieval URLs.
- **Git Safety:** Always prefix Git operations with `DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null`.

## Review Focus

1. **Cold Start (No History):** When a session has 0 prior messages, `0_contextualize_query` must bypass reformulation and pass the question through directly with zero extra latency.
2. **Follow-up Co-reference Resolution:** When asking follow-up questions containing pronouns (*"Nó bằng bao nhiêu?"*, *"Từ kết quả trên tính tiếp..."*), the contextualizer must resolve the subject from history into a complete, standalone question.
3. **Invalid or Corrupt `session_id`:** If a client passes an unknown or malformed `session_id`, the backend must gracefully create a valid new session instead of failing with database foreign key errors.
4. **Cascade Deletion:** Deleting a session via `DELETE /api/v1/sessions/{id}` must cleanly delete all associated messages in SQLite via foreign key cascade.
5. **Thread Switching in React SPA:** Clicking a different conversation in the Sidebar must immediately load that session's messages, update the active session ID, and scroll to the bottom.

---

### Task 1: Persistent SQLite Session Store (`src/storage/session_store.py`)

**Files:**
- Create: `src/storage/session_store.py`
- Create: `tests/test_session_store.py`

**Interfaces:**
- Produces: `SessionStore`:
  - `__init__(db_path: str = "data/chat_history.db")`
  - `create_session(session_id: Optional[str] = None, title: Optional[str] = None) -> str`
  - `get_session(session_id: str) -> Optional[Dict[str, Any]]`
  - `list_sessions(limit: int = 50) -> List[Dict[str, Any]]`
  - `delete_session(session_id: str) -> bool`
  - `add_message(session_id: str, role: str, content: str, standalone_question: Optional[str] = None, citations: Optional[List[Dict[str, Any]]] = None, reasoning_steps: Optional[List[str]] = None) -> str`
  - `get_recent_messages(session_id: str, limit: int = 10) -> List[Dict[str, Any]]`

- [ ] **Step 1: Write the failing session store tests**

Create `tests/test_session_store.py`:
```python
import tempfile
import pytest
from pathlib import Path
from src.storage.session_store import SessionStore

@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_chat.db")
        yield SessionStore(db_path=db_path)

def test_create_and_get_session(store):
    sess_id = store.create_session(title="Câu hỏi máy bơm")
    sess = store.get_session(sess_id)
    assert sess is not None
    assert sess["id"] == sess_id
    assert sess["title"] == "Câu hỏi máy bơm"

def test_add_and_get_messages_sliding_window(store):
    sess_id = store.create_session(title="Test Messages")
    for i in range(15):
        role = "user" if i % 2 == 0 else "assistant"
        store.add_message(sess_id, role=role, content=f"Message {i}")

    recent = store.get_recent_messages(sess_id, limit=10)
    assert len(recent) == 10
    assert recent[0]["content"] == "Message 5"
    assert recent[-1]["content"] == "Message 14"

def test_delete_session_cascades_messages(store):
    sess_id = store.create_session(title="To Delete")
    store.add_message(sess_id, role="user", content="Hello")
    assert store.delete_session(sess_id) is True
    assert store.get_session(sess_id) is None
    assert len(store.get_recent_messages(sess_id, limit=10)) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_session_store.py`
Expected: FAIL (ModuleNotFoundError: No module named 'src.storage.session_store').

- [ ] **Step 3: Implement `SessionStore` in `src/storage/session_store.py`**

- Initialize SQLite database with `PRAGMA foreign_keys = ON;`.
- Create `sessions` and `messages` tables with indices on `session_id, created_at` and `updated_at DESC`.
- Implement `create_session`, `get_session`, `list_sessions`, `delete_session`, `add_message`, `get_recent_messages`.
- In `add_message`: serialize `citations` and `reasoning_steps` as JSON; update session `updated_at`.
- In `get_recent_messages`: retrieve ordered by `created_at ASC` for the last `limit` messages.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_session_store.py`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/storage/ tests/test_session_store.py
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(storage): implement SQLite SessionStore with sliding window and cascade deletion"
```

---

### Task 2: History-Aware Prompting & Contextualizer Node in LangGraph (`src/rag/prompt.py` & `src/rag/agent.py`)

**Files:**
- Modify: `src/rag/prompt.py`
- Modify: `src/rag/agent.py`
- Create: `tests/test_contextualizer.py`

**Interfaces:**
- Consumes: `SessionStore` message dictionaries `[{"role": str, "content": str}]`
- Produces:
  - `CONTEXTUALIZE_QUERY_PROMPT` in `prompt.py`
  - `build_rag_prompt(question, chunks, history=...)` in `prompt.py`
  - `AgentState`: added `history: List[Dict[str, str]]`, `standalone_question: str`
  - `_node_contextualize_query`: reformulates question into standalone query when history exists
  - Updated `AgenticRAG.answer(question, top_k=8, history=None) -> QAResponse`

- [ ] **Step 1: Write the failing contextualizer tests**

Create `tests/test_contextualizer.py`:
```python
import pytest
from unittest.mock import MagicMock
from src.rag.agent import AgenticRAG
from src.models import RetrievalResult, DocumentChunk

@pytest.fixture
def mock_agent():
    mock_retriever = MagicMock()
    mock_chunk = DocumentChunk(chunk_id="c1", doc_name="manual.pdf", page_number=1, text="Cột áp toàn phần H = 35m")
    mock_retriever.retrieve.return_value = [RetrievalResult(chunk=mock_chunk, score=0.9)]
    mock_retriever.hybrid_search.return_value = [RetrievalResult(chunk=mock_chunk, score=0.9)]
    
    mock_llm = MagicMock()
    # Mock contextualizer to reformulate follow-up
    def mock_generate(prompt, **kwargs):
        if "standalone" in prompt.lower() or "viết lại" in prompt.lower():
            return "Cột áp toàn phần H bằng bao nhiêu?"
        return "Cột áp toàn phần H = 35m [Tài liệu: manual.pdf, Trang 1]."
    mock_llm.generate.side_effect = mock_generate
    
    agent = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="mock")
    return agent

def test_contextualize_with_history_rewrites_query(mock_agent):
    history = [
        {"role": "user", "content": "Bơm ly tâm đang thử nghiệm có thông số gì?"},
        {"role": "assistant", "content": "Bơm thử theo TCVN 9222 [Tài liệu: manual.pdf, Trang 1]."}
    ]
    response = mock_agent.answer("Nó có H bằng bao nhiêu?", top_k=5, history=history)
    assert response.standalone_question == "Cột áp toàn phần H bằng bao nhiêu?"
    assert "35m" in response.answer

def test_contextualize_without_history_passes_through(mock_agent):
    response = mock_agent.answer("Tính Reynolds khi D = 0.2m", top_k=5, history=[])
    assert response.standalone_question == "Tính Reynolds khi D = 0.2m"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_contextualizer.py`
Expected: FAIL (argument or attribute not found).

- [ ] **Step 3: Implement contextualization in `src/rag/prompt.py` and `src/rag/agent.py`**

1. In `src/rag/prompt.py`:
   - Define `CONTEXTUALIZE_QUERY_PROMPT`: Instructs LLM to rewrite user question to be standalone given prior conversation history; if question is already self-contained, return as-is.
   - Update `build_rag_prompt(question, chunks, history=None)`: If `history` is provided, append a formatted `LỊCH SỬ TRAO ĐỔI GẦN ĐÂY:` block before `DỮ LIỆU TÀI LIỆU CUNG CẤP:`.
2. In `src/rag/agent.py`:
   - Update `AgentState` with `history: List[Dict[str, str]]` and `standalone_question: str`.
   - Implement `_node_contextualize_query`: If `history` is non-empty, call LLM to formulate standalone question and record in `reasoning_steps: ["0. contextualize: Đã chuẩn hóa câu hỏi theo ngữ cảnh: ..."]`. If no history, set `standalone_question = question`.
   - In graph assembly: Connect `START` -> `0_contextualize_query` -> `1_router`.
   - In subsequent nodes (`2_expand_query`, `3_hybrid_retrieve`, `7_generate`): use `standalone_question`.
   - In `AgenticRAG.answer(question, top_k, history=None)`: accept `history` and return `standalone_question` in `QAResponse`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_contextualizer.py`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/rag/prompt.py src/rag/agent.py tests/test_contextualizer.py
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(rag): add history-aware contextualizer node and conversation prompt formatting"
```

---

### Task 3: API Schemas, Session Routes & Query Endpoint Integration (`src/models.py`, `src/api/routes.py`, `src/api/main.py`)

**Files:**
- Modify: `src/models.py`
- Modify: `src/api/main.py`
- Modify: `src/api/routes.py`
- Create: `tests/test_session_api.py`

**Interfaces:**
- Consumes: `SessionStore`, `AgenticRAG`
- Produces:
  - Models in `src/models.py`: `SessionSummary`, `SessionListResponse`, `SessionDetailResponse`, updated `QARequest(session_id: Optional[str])`, updated `QAResponse(session_id: str, standalone_question: Optional[str])`.
  - Routes in `src/api/routes.py`:
    - `GET /api/v1/sessions`
    - `GET /api/v1/sessions/{session_id}`
    - `DELETE /api/v1/sessions/{session_id}`
    - `POST /api/v1/query` (loads history from `SessionStore`, calls `agent.answer`, persists messages, returns updated `QAResponse`).

- [ ] **Step 1: Write failing API session tests**

Create `tests/test_session_api.py`:
```python
import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.storage.session_store import SessionStore

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "api_test_chat.db")
    app.state.session_store = SessionStore(db_path=db_path)
    with TestClient(app) as test_client:
        yield test_client

def test_session_lifecycle_api(client):
    # 1. Query with no session_id -> creates new session
    res = client.post("/api/v1/query", json={"question": "Chào bạn", "top_k": 5})
    assert res.status_code == 200
    data = res.json()
    sess_id = data["session_id"]
    assert sess_id is not None

    # 2. List sessions
    res_list = client.get("/api/v1/sessions")
    assert res_list.status_code == 200
    sessions = res_list.json()["sessions"]
    assert any(s["id"] == sess_id for s in sessions)

    # 3. Get session detail
    res_detail = client.get(f"/api/v1/sessions/{sess_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert len(detail["messages"]) >= 2
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][1]["role"] == "assistant"

    # 4. Delete session
    res_del = client.delete(f"/api/v1/sessions/{sess_id}")
    assert res_del.status_code == 200
    assert client.get(f"/api/v1/sessions/{sess_id}").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_session_api.py`
Expected: FAIL (404 on /api/v1/sessions).

- [ ] **Step 3: Implement session routes and integrate in `src/api/routes.py` and `main.py`**

1. In `src/models.py`:
   - Add `SessionSummary`, `SessionListResponse`, `SessionDetailResponse`, `ChatMessage`.
   - In `QARequest`: add `session_id: Optional[str] = None`.
   - In `QAResponse`: add `session_id: str`, `standalone_question: Optional[str] = None`.
2. In `src/api/main.py`:
   - Initialize `app.state.session_store = SessionStore()` during startup.
3. In `src/api/routes.py`:
   - Add `GET /api/v1/sessions` returning `SessionListResponse`.
   - Add `GET /api/v1/sessions/{session_id}` returning `SessionDetailResponse` or 404.
   - Add `DELETE /api/v1/sessions/{session_id}` returning status or 404.
   - In `POST /api/v1/query`:
     - Retrieve `session_store` from `request.app.state`.
     - If `session_id` provided and exists, use it; else create a new session with title generated from question (first 40 chars).
     - Fetch recent messages (up to 10) via `session_store.get_recent_messages(session_id, limit=10)`.
     - Pass `history` to `agent.answer(question, top_k, history=recent_messages)`.
     - Save user message and assistant message to `session_store`.
     - Populate `session_id` and `standalone_question` in returned `QAResponse`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_session_api.py`
Expected: PASS (1 passed).

- [ ] **Step 5: Verify all existing backend tests pass**

Run: `.venv/bin/pytest tests/`
Expected: 114+ passed, 0 failed.

- [ ] **Step 6: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/models.py src/api/ tests/test_session_api.py
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(api): add session management routes and multi-turn query integration"
```

---

### Task 4: Frontend API Client & Shared Types (`frontend/src/types/index.ts` & `frontend/src/api/client.ts`)

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: REST endpoints (`/api/v1/sessions`, `/api/v1/sessions/{id}`, `/api/v1/query`)
- Produces:
  - Types: `SessionSummary`, `SessionListResponse`, `SessionDetailResponse`, updated `QAResponse`, updated `ChatMessageData`
  - Functions: `listSessions(): Promise<SessionSummary[]>`, `getSession(sessionId: string): Promise<SessionDetailResponse>`, `deleteSession(sessionId: string): Promise<void>`, updated `askQuestion(question: string, topK?: number, sessionId?: string | null): Promise<QAResponse>`

- [ ] **Step 1: Write failing frontend API tests**

Update `frontend/src/api/client.test.ts`:
```ts
import { listSessions, getSession, deleteSession } from './client';

describe('Session API Client', () => {
  it('listSessions fetches session summaries', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sessions: [{ id: 's1', title: 'Máy bơm', created_at: '', updated_at: '' }] }),
    } as Response);

    const res = await listSessions();
    expect(res).toHaveLength(1);
    expect(res[0].id).toBe('s1');
  });

  it('deleteSession sends DELETE to /api/v1/sessions/{id}', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success' }),
    } as Response);

    await deleteSession('s1');
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/sessions/s1', expect.objectContaining({ method: 'DELETE' }));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- --run src/api/client.test.ts`
Expected: FAIL (listSessions is not defined).

- [ ] **Step 3: Update `frontend/src/types/index.ts` and `frontend/src/api/client.ts`**

- In `frontend/src/types/index.ts`:
  - Export `SessionSummary`, `SessionListResponse`, `SessionDetailResponse`.
  - Add `session_id?: string` and `standalone_question?: string` to `QAResponse`.
  - Add `standalone_question?: string` to `ChatMessageData`.
- In `frontend/src/api/client.ts`:
  - Implement `listSessions(): Promise<SessionSummary[]>`.
  - Implement `getSession(sessionId: string): Promise<SessionDetailResponse>`.
  - Implement `deleteSession(sessionId: string): Promise<void>`.
  - In `askQuestion(question, topK, sessionId)`: pass `session_id: sessionId || undefined` in POST JSON body.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- --run src/api/client.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add frontend/src/types/ frontend/src/api/
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(frontend): add session client methods and data models"
```

---

### Task 5: Frontend React UI Integration (Sidebar Session List & Multi-turn Chat Sync)

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Modify: `frontend/src/components/chat/ChatMessage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/Sidebar.test.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `SessionSummary`, `SessionDetailResponse`, `listSessions`, `getSession`, `deleteSession`
- Produces:
  - Sidebar: "Cuộc trò chuyện gần đây" listing previous sessions with click-to-load and delete action.
  - ChatMessage: displays `standalone_question` tag when query was reformulated.
  - App: maintains `currentSessionId`, loads active session messages, switches sessions seamlessly.

- [ ] **Step 1: Write failing UI tests for sessions in Sidebar and App**

Update `frontend/src/components/layout/Sidebar.test.tsx`:
```tsx
it('renders recent chat sessions and allows switching session', () => {
  const onSelectSession = vi.fn();
  const sessions = [{ id: 's1', title: 'Tính Reynolds', created_at: '', updated_at: '' }];
  render(
    <Sidebar
      isOpen={true}
      onClose={vi.fn()}
      files={[]}
      topK={8}
      onTopKChange={vi.fn()}
      onNewChat={vi.fn()}
      onFileUpload={vi.fn()}
      onDeleteFile={vi.fn()}
      sessions={sessions}
      activeSessionId="s1"
      onSelectSession={onSelectSession}
      onDeleteSession={vi.fn()}
    />
  );
  expect(screen.getByText('Tính Reynolds')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Tính Reynolds'));
  expect(onSelectSession).toHaveBeenCalledWith('s1');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- --run src/components/layout/Sidebar.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement Session List in Sidebar and wire up in App.tsx**

1. In `Sidebar.tsx`:
   - Add `sessions: SessionSummary[]`, `activeSessionId: string | null`, `onSelectSession: (id: string) => void`, `onDeleteSession: (id: string) => Promise<void>` to props.
   - Add a "Cuộc trò chuyện gần đây" scrollable section below "Cuộc trò chuyện mới".
   - Each session card renders `MessageSquare` icon, truncated `title`, active highlight state (`border-obsidian-accent-blue/40`), and delete button with `window.confirm`.
2. In `ChatMessage.tsx`:
   - If `message.standalone_question && message.standalone_question !== message.content`: render subtle context badge:
     `🔍 Ngữ cảnh suy luận: "${message.standalone_question}"`.
3. In `App.tsx`:
   - Add state: `sessions: SessionSummary[]`, `currentSessionId: string | null`.
   - On mount: call `listSessions()`, read `localStorage.getItem('active_session_id')`, if present load session messages with `getSession(id)`.
   - In `handleSendMessage`: pass `currentSessionId` to `askQuestion`. If response returns `session_id`, set `currentSessionId`, store in `localStorage`, and refresh session list.
   - In `handleNewChat`: set `currentSessionId = null`, clear `localStorage`, clear `messages`.
   - In `handleSelectSession(id)`: load messages from `getSession(id)`, set `currentSessionId = id`, store in `localStorage`.
   - In `handleDeleteSession(id)`: call `deleteSession(id)`, if deleted session is `currentSessionId`, reset to new chat; refresh `sessions` list.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- --run`
Expected: PASS (all frontend tests pass).

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add frontend/src/
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(frontend): integrate session history in sidebar and multi-turn chat management"
```

---

### Task 6: Streamlit UI Update, Full Regression & Documentation

**Files:**
- Modify: `src/ui/api_client.py`
- Modify: `src/ui/app.py`
- Modify: `README.md`
- Test: All backend pytest + all frontend Vitest tests

**Interfaces:**
- Consumes: Complete multi-turn API
- Produces: Updated Streamlit client passing `session_id`, updated `README.md` documenting session management REST API, 100% verified test suites.

- [ ] **Step 1: Update Streamlit client and app**

- In `src/ui/api_client.py`: accept `session_id: Optional[str] = None` in `query_assistant`.
- In `src/ui/app.py`: maintain `st.session_state["session_id"]`, pass to `query_assistant`, update from response.

- [ ] **Step 2: Run all backend pytest tests**

Run: `.venv/bin/pytest tests/`
Expected: 114+ passed, 0 failed.

- [ ] **Step 3: Run all frontend Vitest tests**

Run: `cd frontend && npm run test -- --run`
Expected: 100% passed.

- [ ] **Step 4: Run frontend production build**

Run: `cd frontend && npm run build`
Expected: Clean build with 0 errors.

- [ ] **Step 5: Update README.md**

Document the new session endpoints (`GET /api/v1/sessions`, `GET /api/v1/sessions/{id}`, `DELETE /api/v1/sessions/{id}`) and the multi-turn conversational query flow.

- [ ] **Step 6: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/ui/ README.md
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "docs: document multi-turn conversation session API and update Streamlit companion"
```

