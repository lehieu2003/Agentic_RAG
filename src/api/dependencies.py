"""Shared dependencies and helpers for the API routers."""

from pathlib import Path

from fastapi import Request

from src.config import settings
from src.storage.session_store import SessionStore

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}


def _get_upload_dir() -> Path:
    """Ensure and return the upload directory path from settings."""
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


def get_session_store(request: Request) -> SessionStore:
    """Return the app-level session store, creating it on first use."""
    session_store = getattr(request.app.state, "session_store", None)
    if session_store is None:
        session_store = SessionStore()
        request.app.state.session_store = session_store
    return session_store
