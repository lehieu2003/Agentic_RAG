import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.config import settings
from src.storage.session_store import SessionStore


@pytest.fixture(scope="module", autouse=True)
def isolated_upload_dir(tmp_path_factory):
    upload_dir = tmp_path_factory.mktemp("uploads")
    original = settings.upload_dir
    settings.upload_dir = str(upload_dir)
    yield upload_dir
    settings.upload_dir = original


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("db") / "api_test_chat.db")
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
    assert "standalone_question" in data

    # 2. List sessions
    res_list = client.get("/api/v1/sessions")
    assert res_list.status_code == 200
    sessions = res_list.json()["sessions"]
    assert any(s["id"] == sess_id for s in sessions)

    # 3. Get session detail
    res_detail = client.get(f"/api/v1/sessions/{sess_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["session"]["id"] == sess_id
    assert len(detail["messages"]) >= 2
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][0]["content"] == "Chào bạn"
    assert detail["messages"][1]["role"] == "assistant"

    # 4. Delete session
    res_del = client.delete(f"/api/v1/sessions/{sess_id}")
    assert res_del.status_code == 200
    assert client.get(f"/api/v1/sessions/{sess_id}").status_code == 404


def test_get_nonexistent_session_returns_404(client):
    res = client.get("/api/v1/sessions/nonexistent-session-id")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_delete_nonexistent_session_returns_404(client):
    res = client.delete("/api/v1/sessions/nonexistent-session-id")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_query_with_existing_session_id_multi_turn(client):
    # First turn
    res1 = client.post("/api/v1/query", json={"question": "Xin chào bot", "top_k": 3})
    assert res1.status_code == 200
    sess_id = res1.json()["session_id"]

    # Second turn with existing session_id
    res2 = client.post(
        "/api/v1/query",
        json={"question": "Bạn có thể làm gì?", "top_k": 3, "session_id": sess_id},
    )
    assert res2.status_code == 200
    assert res2.json()["session_id"] == sess_id

    # Verify session detail contains all 4 messages
    res_detail = client.get(f"/api/v1/sessions/{sess_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    messages = detail["messages"]
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[3]["role"] == "assistant"


def test_query_with_explicit_new_session_id(client):
    custom_id = "custom-session-uuid-1234"
    res = client.post(
        "/api/v1/query",
        json={"question": "Chào bạn", "top_k": 3, "session_id": custom_id},
    )
    assert res.status_code == 200
    assert res.json()["session_id"] == custom_id

    # Verify session exists
    res_detail = client.get(f"/api/v1/sessions/{custom_id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["session"]["id"] == custom_id


def test_list_sessions_with_limit_param(client):
    # Create multiple sessions
    for i in range(3):
        client.post(
            "/api/v1/query",
            json={"question": f"Câu hỏi {i}", "top_k": 1, "session_id": f"sess-limit-{i}"},
        )

    res_all = client.get("/api/v1/sessions?limit=2")
    assert res_all.status_code == 200
    sessions = res_all.json()["sessions"]
    assert len(sessions) == 2


def test_delete_all_sessions_api(client):
    client.post("/api/v1/query", json={"question": "Q1", "session_id": "del-all-1"})
    client.post("/api/v1/query", json={"question": "Q2", "session_id": "del-all-2"})

    res = client.delete("/api/v1/sessions")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["deleted_count"] >= 2

    list_res = client.get("/api/v1/sessions")
    assert list_res.status_code == 200
    assert len(list_res.json()["sessions"]) == 0


def test_batch_delete_sessions_api(client):
    client.post("/api/v1/query", json={"question": "Q1", "session_id": "batch-1"})
    client.post("/api/v1/query", json={"question": "Q2", "session_id": "batch-2"})
    client.post("/api/v1/query", json={"question": "Q3", "session_id": "batch-3"})

    res = client.post(
        "/api/v1/sessions/batch-delete",
        json={"session_ids": ["batch-1", "batch-3"]},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["deleted_count"] == 2

    assert client.get("/api/v1/sessions/batch-1").status_code == 404
    assert client.get("/api/v1/sessions/batch-3").status_code == 404
    assert client.get("/api/v1/sessions/batch-2").status_code == 200

