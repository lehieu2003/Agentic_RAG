"""API Client wrapper communicating with FastAPI backend."""

import mimetypes
from typing import Any, Dict, List, Optional
import httpx
from src.models import QAResponse


class ApiClient:
    """HTTP Client for Document Q&A Assistant FastAPI service."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api/v1",
        timeout: float = 120.0,
        upload_timeout: float = 600.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.upload_timeout = upload_timeout

    def check_health(self) -> Optional[Dict[str, Any]]:
        """Check system health status.

        Returns:
            Dict containing status payload or None if connection fails.
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.base_url}/health")
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    def list_files(self) -> List[Dict[str, Any]]:
        """List all permanently stored documents on the server.

        Returns:
            List of file metadata dicts, or empty list if request fails.
        """
        try:
            url = f"{self.base_url}/files" if self.base_url.endswith("/api/v1") else f"{self.base_url}/api/v1/files"
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        return data
                return []
        except Exception:
            return []

    def delete_file(self, filename: str) -> bool:
        """Delete a document from backend storage and vector index.

        Args:
            filename: Name of the file to delete.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            url = f"{self.base_url}/files/{filename}" if self.base_url.endswith("/api/v1") else f"{self.base_url}/api/v1/files/{filename}"
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.delete(url)
                return resp.status_code == 200
        except Exception:
            return False

    def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Upload a document file to the backend for OCR and vector indexing.

        Args:
            file_bytes: Raw binary bytes of the document file.
            filename: Original filename.
            timeout: Optional custom timeout in seconds (defaults to upload_timeout=600s).

        Returns:
            Dict containing upload and indexing result.

        Raises:
            RuntimeError: If request fails or server returns an error.
        """
        use_timeout = timeout or self.upload_timeout
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with httpx.Client(timeout=use_timeout) as client:
            files = {"file": (filename, file_bytes, content_type)}
            resp = client.post(f"{self.base_url}/upload", files=files)
            if resp.status_code >= 400:
                raise RuntimeError(f"API Error ({resp.status_code}): {resp.text}")
            return resp.json()

    def query(
        self,
        question: str,
        top_k: int = 3,
        session_id: Optional[str] = None,
    ) -> QAResponse:
        """Submit a user question to the Q&A assistant.

        Args:
            question: User natural language query.
            top_k: Number of relevant chunks to retrieve.
            session_id: Optional session identifier for multi-turn conversation context.

        Returns:
            Parsed QAResponse model.

        Raises:
            Exception: If request fails or server returns an error.
        """
        with httpx.Client(timeout=self.timeout) as client:
            payload: Dict[str, Any] = {"question": question, "top_k": top_k}
            if session_id:
                payload["session_id"] = session_id
            resp = client.post(f"{self.base_url}/query", json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"API Error ({resp.status_code}): {resp.text}")
            return QAResponse.model_validate(resp.json())

    # Alias query_assistant to query for backward and cross-compatibility
    query_assistant = query

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List active conversation sessions from backend.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of session summary dicts, or empty list if request fails.
        """
        try:
            url = f"{self.base_url}/sessions" if self.base_url.endswith("/api/v1") else f"{self.base_url}/api/v1/sessions"
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params={"limit": limit})
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "sessions" in data:
                        return data["sessions"]
                return []
        except Exception:
            return []

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detail and message history of a session.

        Args:
            session_id: Session identifier.

        Returns:
            Session detail dict or None.
        """
        try:
            url = f"{self.base_url}/sessions/{session_id}" if self.base_url.endswith("/api/v1") else f"{self.base_url}/api/v1/sessions/{session_id}"
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a conversation session.

        Args:
            session_id: Session identifier.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            url = f"{self.base_url}/sessions/{session_id}" if self.base_url.endswith("/api/v1") else f"{self.base_url}/api/v1/sessions/{session_id}"
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.delete(url)
                return resp.status_code == 200
        except Exception:
            return False
