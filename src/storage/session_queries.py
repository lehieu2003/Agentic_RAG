"""Session-level persistence operations for :class:`SessionStore`."""

from typing import Any, Dict, List, Optional
import uuid


class SessionQueriesMixin:
    """Create, read, and delete chat session rows."""

    def create_session(
        self, session_id: Optional[str] = None, title: Optional[str] = None
    ) -> str:
        """Create a new chat session or update title if existing.

        Args:
            session_id: Optional explicit session ID (UUID string generated if None).
            title: Title of session (defaults to 'Cuộc trò chuyện mới').

        Returns:
            The session ID string.
        """
        sid = session_id or str(uuid.uuid4())
        session_title = title or "Cuộc trò chuyện mới"

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, title, created_at, updated_at)
                VALUES (?, ?, (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')), (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')))
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    updated_at = (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
                """,
                (sid, session_title),
            )
        return sid

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a session's metadata by ID.

        Args:
            session_id: The session ID.

        Returns:
            Dictionary containing session metadata, or None if not found.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?;",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "id": str(row["id"]),
                "title": str(row["title"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent chat sessions ordered by updated_at DESC.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of session metadata dictionaries.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC, rowid DESC
                LIMIT ?;
                """,
                (limit,),
            ).fetchall()
            return [
                {
                    "id": str(row["id"]),
                    "title": str(row["title"]),
                    "created_at": str(row["created_at"]),
                    "updated_at": str(row["updated_at"]),
                }
                for row in rows
            ]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its cascading messages.

        Args:
            session_id: The session ID to delete.

        Returns:
            True if session was found and deleted, False otherwise.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?;", (session_id,))
            return cursor.rowcount > 0

    def delete_all_sessions(self) -> int:
        """Delete all sessions and their cascading messages.

        Returns:
            Number of deleted sessions.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions;")
            return cursor.rowcount

    def delete_sessions(self, session_ids: List[str]) -> int:
        """Delete multiple sessions by IDs and their cascading messages.

        Args:
            session_ids: List of session IDs to delete.

        Returns:
            Number of deleted sessions.
        """
        if not session_ids:
            return 0
        with self._get_connection() as conn:
            placeholders = ",".join(["?"] * len(session_ids))
            cursor = conn.execute(
                f"DELETE FROM sessions WHERE id IN ({placeholders});",
                tuple(session_ids),
            )
            return cursor.rowcount
