"""Persistent SQLite Session Store for Multi-Turn Conversation Memory.

Connection management and schema creation live here; the session and message
queries are provided by :class:`SessionQueriesMixin` and
:class:`MessageQueriesMixin`.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from src.storage.message_queries import MessageQueriesMixin
from src.storage.schema import SCHEMA_SQL
from src.storage.session_queries import SessionQueriesMixin


class SessionStore(SessionQueriesMixin, MessageQueriesMixin):
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

            conn.executescript(SCHEMA_SQL)
