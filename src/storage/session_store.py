"""Persistent SQLite Session Store for Multi-Turn Conversation Memory."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


class SessionStore:
    """Manages chat sessions and conversation history using SQLite."""

    def __init__(self, db_path: str = "data/chat_history.db") -> None:
        """Initialize SQLite database, ensuring directory exists and schema is created.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = str(db_path)
        # Ensure parent directories exist
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for SQLite database connection.

        Configures foreign key support, row factory, and handles commit/rollback.
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create tables and indices if they do not exist."""
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    standalone_question TEXT,
                    citations_json TEXT,
                    reasoning_steps_json TEXT,
                    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC);
                """
            )

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

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        standalone_question: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        reasoning_steps: Optional[List[str]] = None,
    ) -> str:
        """Add a message to a session history and update session's updated_at.

        Args:
            session_id: Target session ID.
            role: 'user' or 'assistant'.
            content: Text content of message.
            standalone_question: Optional rewritten standalone query.
            citations: Optional list of citation dictionaries or models.
            reasoning_steps: Optional list of intermediate reasoning step strings.

        Returns:
            Generated message ID.
        """
        if role not in ("user", "assistant"):
            raise ValueError(f"Invalid role '{role}'. Must be 'user' or 'assistant'.")

        msg_id = str(uuid.uuid4())

        citations_json: Optional[str] = None
        if citations is not None:
            serialized_citations = []
            for c in citations:
                if hasattr(c, "model_dump"):
                    serialized_citations.append(c.model_dump())
                elif hasattr(c, "dict"):
                    serialized_citations.append(c.dict())
                else:
                    serialized_citations.append(c)
            citations_json = json.dumps(serialized_citations, ensure_ascii=False)

        reasoning_steps_json: Optional[str] = None
        if reasoning_steps is not None:
            reasoning_steps_json = json.dumps(list(reasoning_steps), ensure_ascii=False)

        with self._get_connection() as conn:
            # Ensure session exists (auto-create if unknown/missing)
            default_title = content[:40].strip() if content else "Cuộc trò chuyện mới"
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at)
                VALUES (?, ?, (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')), (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')));
                """,
                (session_id, default_title or "Cuộc trò chuyện mới"),
            )

            # Insert message
            conn.execute(
                """
                INSERT INTO messages (
                    id, session_id, role, content, standalone_question,
                    citations_json, reasoning_steps_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')));
                """,
                (
                    msg_id,
                    session_id,
                    role,
                    content,
                    standalone_question,
                    citations_json,
                    reasoning_steps_json,
                ),
            )

            # Update session timestamp
            conn.execute(
                "UPDATE sessions SET updated_at = (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')) WHERE id = ?;",
                (session_id,),
            )

        return msg_id

    def get_recent_messages(
        self, session_id: str, limit: Optional[int] = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve recent messages for a session in chronological order (ASC).

        Args:
            session_id: Session ID to retrieve messages for.
            limit: Maximum messages to retrieve. If None or <= 0, returns all messages.

        Returns:
            List of message dictionaries ordered chronologically.
        """
        with self._get_connection() as conn:
            if limit is not None and limit > 0:
                rows = conn.execute(
                    """
                    SELECT id, session_id, role, content, standalone_question,
                           citations_json, reasoning_steps_json, created_at
                    FROM (
                        SELECT rowid, id, session_id, role, content, standalone_question,
                               citations_json, reasoning_steps_json, created_at
                        FROM messages
                        WHERE session_id = ?
                        ORDER BY created_at DESC, rowid DESC
                        LIMIT ?
                    )
                    ORDER BY created_at ASC, rowid ASC;
                    """,
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, session_id, role, content, standalone_question,
                           citations_json, reasoning_steps_json, created_at
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY created_at ASC, rowid ASC;
                    """,
                    (session_id,),
                ).fetchall()

            messages: List[Dict[str, Any]] = []
            for row in rows:
                citations = (
                    json.loads(row["citations_json"])
                    if row["citations_json"]
                    else None
                )
                reasoning_steps = (
                    json.loads(row["reasoning_steps_json"])
                    if row["reasoning_steps_json"]
                    else None
                )
                messages.append(
                    {
                        "id": str(row["id"]),
                        "session_id": str(row["session_id"]),
                        "role": str(row["role"]),
                        "content": str(row["content"]),
                        "standalone_question": row["standalone_question"],
                        "citations": citations,
                        "reasoning_steps": reasoning_steps,
                        "created_at": str(row["created_at"]),
                    }
                )
            return messages

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all messages for a session in chronological order (ASC).

        Args:
            session_id: Session ID to retrieve messages for.

        Returns:
            Full list of message dictionaries.
        """
        return self.get_recent_messages(session_id, limit=None)
