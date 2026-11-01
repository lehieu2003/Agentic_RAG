import re
import tempfile
import pytest
from pathlib import Path
from src.storage.session_store import SessionStore

ISO_8601_REGEX = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "nested" / "dir" / "test_chat.db")
        yield SessionStore(db_path=db_path)


def test_create_and_get_session(store):
    sess_id = store.create_session(title="Câu hỏi máy bơm")
    sess = store.get_session(sess_id)
    assert sess is not None
    assert sess["id"] == sess_id
    assert sess["title"] == "Câu hỏi máy bơm"
    assert "created_at" in sess
    assert "updated_at" in sess
    assert bool(re.match(ISO_8601_REGEX, sess["created_at"]))
    assert bool(re.match(ISO_8601_REGEX, sess["updated_at"]))


def test_create_session_defaults(store):
    sess_id = store.create_session()
    sess = store.get_session(sess_id)
    assert sess is not None
    assert sess["id"] == sess_id
    assert sess["title"] == "Cuộc trò chuyện mới"


def test_create_session_custom_id(store):
    custom_id = "custom-session-uuid-1234"
    returned_id = store.create_session(session_id=custom_id, title="Custom Session")
    assert returned_id == custom_id
    sess = store.get_session(custom_id)
    assert sess is not None
    assert sess["title"] == "Custom Session"


def test_get_session_not_found(store):
    assert store.get_session("non-existent-session-id") is None


def test_add_and_get_messages_sliding_window(store):
    sess_id = store.create_session(title="Test Messages")
    for i in range(15):
        role = "user" if i % 2 == 0 else "assistant"
        store.add_message(sess_id, role=role, content=f"Message {i}")

    recent = store.get_recent_messages(sess_id, limit=10)
    assert len(recent) == 10
    assert recent[0]["content"] == "Message 5"
    assert recent[-1]["content"] == "Message 14"


def test_add_message_with_metadata(store):
    sess_id = store.create_session(title="Metadata Session")
    msg_id = store.add_message(
        session_id=sess_id,
        role="assistant",
        content="Độ nhớt động lực học là 0.001 Pa.s",
        standalone_question="Độ nhớt động lực học của nước ở 20 độ C là bao nhiêu?",
        citations=[{"doc_name": "tcvn_pump.pdf", "page_number": 12}],
        reasoning_steps=["Tra bảng 2 tiêu chuẩn TCVN", "Lấy giá trị tại 20°C"],
    )
    assert isinstance(msg_id, str) and len(msg_id) > 0

    messages = store.get_recent_messages(sess_id, limit=5)
    assert len(messages) == 1
    msg = messages[0]
    assert msg["id"] == msg_id
    assert msg["role"] == "assistant"
    assert msg["content"] == "Độ nhớt động lực học là 0.001 Pa.s"
    assert msg["standalone_question"] == "Độ nhớt động lực học của nước ở 20 độ C là bao nhiêu?"
    assert msg["citations"] == [{"doc_name": "tcvn_pump.pdf", "page_number": 12}]
    assert msg["reasoning_steps"] == ["Tra bảng 2 tiêu chuẩn TCVN", "Lấy giá trị tại 20°C"]
    assert bool(re.match(ISO_8601_REGEX, msg["created_at"]))


def test_list_sessions(store):
    store.create_session(session_id="s1", title="Session 1")
    store.create_session(session_id="s2", title="Session 2")
    sessions = store.list_sessions(limit=10)
    assert len(sessions) == 2
    session_ids = [s["id"] for s in sessions]
    assert "s1" in session_ids
    assert "s2" in session_ids


def test_delete_session_cascades_messages(store):
    sess_id = store.create_session(title="To Delete")
    store.add_message(sess_id, role="user", content="Hello")
    assert store.delete_session(sess_id) is True
    assert store.get_session(sess_id) is None
    assert len(store.get_recent_messages(sess_id, limit=10)) == 0


def test_delete_non_existent_session(store):
    assert store.delete_session("does-not-exist") is False


def test_delete_all_sessions(store):
    store.create_session(session_id="s1", title="Session 1")
    store.create_session(session_id="s2", title="Session 2")
    store.add_message("s1", role="user", content="Hi 1")
    store.add_message("s2", role="user", content="Hi 2")

    deleted_count = store.delete_all_sessions()
    assert deleted_count == 2
    assert len(store.list_sessions()) == 0
    assert len(store.get_messages("s1")) == 0
    assert len(store.get_messages("s2")) == 0


def test_delete_sessions_batch(store):
    store.create_session(session_id="s1", title="Session 1")
    store.create_session(session_id="s2", title="Session 2")
    store.create_session(session_id="s3", title="Session 3")
    store.add_message("s1", role="user", content="Hi 1")
    store.add_message("s2", role="user", content="Hi 2")
    store.add_message("s3", role="user", content="Hi 3")

    deleted_count = store.delete_sessions(["s1", "s3"])
    assert deleted_count == 2
    remaining = store.list_sessions()
    assert len(remaining) == 1
    assert remaining[0]["id"] == "s2"
    assert len(store.get_messages("s1")) == 0
    assert len(store.get_messages("s3")) == 0
    assert len(store.get_messages("s2")) == 1


def test_delete_sessions_batch_empty_or_not_found(store):
    assert store.delete_sessions([]) == 0
    assert store.delete_sessions(["non-existent-id"]) == 0
