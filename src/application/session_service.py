"""Chat session use-cases: list, inspect, and delete conversations."""

from typing import Any, Dict, List

from src.domain.exceptions import NotFoundError
from src.models import (
    ChatMessage,
    SessionDetailResponse,
    SessionListResponse,
    SessionSummary,
)
from src.rag.generator import strip_citation_markers
from src.storage.session_store import SessionStore


class SessionService:
    """Reads and manages conversation sessions backed by the session store."""

    def __init__(self, session_store: SessionStore) -> None:
        self._session_store = session_store

    def list_sessions(self, limit: int) -> SessionListResponse:
        """List sessions ordered by most recent update."""
        sessions_raw = self._session_store.list_sessions(limit=limit)
        sessions = [
            SessionSummary(
                id=s["id"],
                title=s["title"],
                created_at=str(s["created_at"]),
                updated_at=str(s["updated_at"]),
            )
            for s in sessions_raw
        ]
        return SessionListResponse(sessions=sessions)

    def get_session_detail(self, session_id: str) -> SessionDetailResponse:
        """Return a session with its full message history."""
        sess_raw = self._session_store.get_session(session_id)
        if not sess_raw:
            raise NotFoundError("Session not found")

        messages_raw = self._session_store.get_messages(session_id)
        # Messages saved before inline markers were stripped still contain them.
        messages = [
            ChatMessage(**{**m, "content": strip_citation_markers(m["content"]) or m["content"]})
            if m.get("role") == "assistant" and m.get("citations")
            else ChatMessage(**m)
            for m in messages_raw
        ]
        return SessionDetailResponse(
            session=SessionSummary(**sess_raw),
            messages=messages,
        )

    def delete_session(self, session_id: str) -> Dict[str, Any]:
        """Delete one session and all of its messages."""
        deleted = self._session_store.delete_session(session_id)
        if not deleted:
            raise NotFoundError("Session not found")

        return {
            "status": "success",
            "session_id": session_id,
            "message": f"Đã xoá phiên hội thoại '{session_id}' thành công."
        }

    def delete_all_sessions(self) -> Dict[str, Any]:
        """Delete every session and message."""
        deleted_count = self._session_store.delete_all_sessions()
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": f"Đã xoá toàn bộ {deleted_count} phiên hội thoại thành công."
        }

    def delete_sessions_batch(self, session_ids: List[str]) -> Dict[str, Any]:
        """Delete the given sessions by id."""
        deleted_count = self._session_store.delete_sessions(session_ids)
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": f"Đã xoá {deleted_count} phiên hội thoại thành công."
        }


__all__ = ["SessionService"]
