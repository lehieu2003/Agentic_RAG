"""Message persistence operations for :class:`SessionStore`."""

import json
from typing import Any, Dict, List, Optional
import uuid


class MessageQueriesMixin:
    """Append and read conversation messages for a session."""

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
