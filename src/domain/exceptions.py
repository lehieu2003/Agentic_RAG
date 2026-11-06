"""Business-rule errors shared across the application layer.

Services raise these instead of FastAPI's ``HTTPException`` so the
application layer stays framework-free; ``src.api.error_handlers`` maps
them onto the HTTP ``{"detail": ...}`` contract in a single place.
"""

from typing import Optional


class DomainError(Exception):
    """Base class for business-rule violations.

    Subclasses set ``status_code`` (the HTTP status the API edge should
    respond with) and ``default_detail``. A specific message can be
    supplied per raise; otherwise the class default is used.
    """

    status_code: int = 400
    default_detail: str = "Request cannot be processed."

    def __init__(self, detail: Optional[str] = None) -> None:
        self.detail = detail if detail is not None else self.default_detail
        super().__init__(self.detail)


class UnsupportedFileTypeError(DomainError):
    """Uploaded file has an extension outside the supported set."""

    status_code = 400
    default_detail = "Unsupported file format."


class DocumentExtractionError(DomainError):
    """Document is corrupted or yielded no extractable text."""

    status_code = 400
    default_detail = "Failed to extract text from document."


class IndexingNotSupportedError(DomainError):
    """Active retrieval backend cannot index new documents."""

    status_code = 501
    default_detail = "Document indexing is not supported by the active retrieval backend."


class RetrievalError(DomainError):
    """Retrieval or generation pipeline failed at request time."""

    status_code = 503
    default_detail = "Retrieval failure."


class UploadTooLargeError(DomainError):
    """Uploaded file exceeds the configured size limit."""

    status_code = 413
    default_detail = "Uploaded file is too large."


class NotFoundError(DomainError):
    """Requested resource does not exist."""

    status_code = 404
    default_detail = "Resource not found."
