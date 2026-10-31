"""API Client wrapper communicating with FastAPI backend."""

import mimetypes
from typing import Any, Dict, Optional
import httpx
from src.models import QAResponse


class ApiClient:
    """HTTP Client for Document Q&A Assistant FastAPI service."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api/v1",
        timeout: float = 60.0,
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

    def query(self, question: str, top_k: int = 3) -> QAResponse:
        """Submit a user question to the Q&A assistant.

        Args:
            question: User natural language query.
            top_k: Number of relevant chunks to retrieve.

        Returns:
            Parsed QAResponse model.

        Raises:
            Exception: If request fails or server returns an error.
        """
        with httpx.Client(timeout=self.timeout) as client:
            payload = {"question": question, "top_k": top_k}
            resp = client.post(f"{self.base_url}/query", json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"API Error ({resp.status_code}): {resp.text}")
            return QAResponse.model_validate(resp.json())
