"""Document ingestion use-cases: upload, list, locate, and delete.

Pipeline orchestration extracted from the API router so the web layer only
parses requests. All business-rule failures raise
``src.domain.exceptions``; HTTP mapping happens at the API edge.
"""

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional
import unicodedata
import uuid

from src.config import settings
from src.domain.exceptions import (
    DocumentExtractionError,
    DomainError,
    IndexingNotSupportedError,
    NotFoundError,
    RetrievalError,
    UploadTooLargeError,
    UnsupportedFileTypeError,
)
from src.ingestion.chunker import chunk_document
from src.ingestion.document_extractor import extract_pages_from_document
from src.ingestion.tokenization import get_chunk_token_limit
from src.models import FileSummary, IngestionJobResponse, IngestionJobStatus, UploadResponse
from src.retrieval.base import BaseRetriever

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}


class IngestionService:
    """Owns the document lifecycle: storage, extraction, chunking, indexing."""

    def __init__(
        self,
        retriever: Optional[BaseRetriever] = None,
        ocr_engine: Any = None,
        embedding_model: Any = None,
    ) -> None:
        """Wire the collaborators resolved from ``app.state``.

        ``retriever``/``ocr_engine``/``embedding_model`` may be ``None`` when
        the application is starting up; read-style use-cases still work and
        ingestion reports a clear error instead.
        """
        self._retriever = retriever
        self._ocr_engine = ocr_engine
        self._embedding_model = embedding_model

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _get_upload_dir() -> Path:
        """Ensure and return the upload directory path from settings."""
        upload_path = Path(settings.upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)
        return upload_path

    def _resolve_file(self, safe_filename: str) -> Optional[Path]:
        """Locate an uploaded file, tolerating Unicode naming differences.

        Falls back to a directory scan comparing NFC-normalized names, so a
        file stored under a differently-normalized byte sequence still matches.
        """
        upload_dir = self._get_upload_dir()
        file_path = upload_dir / safe_filename
        if file_path.is_file():
            return file_path
        for cand in upload_dir.iterdir():
            if cand.is_file() and unicodedata.normalize("NFC", cand.name) == safe_filename:
                return cand
        return None

    # ------------------------------------------------------------------ #
    # Use-cases
    # ------------------------------------------------------------------ #
    def ingest(self, filename: Optional[str], fileobj: BinaryIO) -> UploadResponse:
        """Store, extract, chunk, and index an uploaded document (synchronous).

        Raises :class:`UnsupportedFileTypeError`, :class:`DocumentExtractionError`,
        :class:`IndexingNotSupportedError`, or :class:`RetrievalError` on failure;
        a partially stored file is removed before the error propagates.
        """
        safe_filename, target_path, duplicate = self._store_upload(filename, fileobj)
        if duplicate:
            return self._already_exists_response(safe_filename)
        return self._process_stored_file(safe_filename, target_path, filename)

    def start_ingestion_job(
        self,
        filename: Optional[str],
        fileobj: BinaryIO,
        job_store,
    ) -> IngestionJobResponse:
        """Store the upload and register a background job for heavy processing.

        The synchronous part is deliberately tiny (validation + durable file
        write) so the HTTP response returns fast; extraction, OCR, chunking,
        and indexing happen in :meth:`run_ingestion_job`.
        """
        safe_filename, _target_path, duplicate = self._store_upload(filename, fileobj)
        job = job_store.create(safe_filename, job_id=uuid.uuid4().hex)
        if duplicate:
            job_store.mark_finished(
                job.job_id,
                IngestionJobStatus.ALREADY_EXISTS,
                result=self._already_exists_response(safe_filename),
            )
            return job_store.get(job.job_id)
        return job

    def run_ingestion_job(self, job_id: str, job_store) -> None:
        """Process a stored upload in the background and update the job record."""
        job = job_store.get(job_id)
        if job is None:
            return
        job_store.mark_running(job_id)

        target_path = self._resolve_file(job.filename)
        if target_path is None:
            job_store.mark_finished(
                job_id,
                IngestionJobStatus.FAILED,
                error=f"Stored file '{job.filename}' disappeared before processing.",
            )
            return

        try:
            result = self._process_stored_file(job.filename, target_path, job.filename)
            job_store.mark_finished(job_id, IngestionJobStatus.SUCCESS, result=result)
        except Exception as e:
            logger.warning("Background ingestion of '%s' failed: %s", job.filename, e)
            detail = e.detail if isinstance(e, DomainError) else str(e)
            job_store.mark_finished(job_id, IngestionJobStatus.FAILED, error=detail)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _already_exists_response(safe_filename: str) -> UploadResponse:
        return UploadResponse(
            filename=safe_filename,
            pages_extracted=0,
            pages_digital=0,
            pages_scanned_ocr=0,
            chunks_indexed=0,
            status="already_exists",
            message=f"Tài liệu '{safe_filename}' đã tồn tại trên hệ thống. Bỏ qua nạp trùng lặp."
        )

    def _store_upload(self, filename: Optional[str], fileobj: BinaryIO):
        """Validate, deduplicate, and durably store the raw upload.

        Returns ``(safe_filename, target_path, duplicate)``. Raises
        :class:`UnsupportedFileTypeError` / :class:`RetrievalError` /
        :class:`UploadTooLargeError`.
        """
        raw_filename = Path(filename).name if filename else "uploaded_document"
        safe_filename = unicodedata.normalize("NFC", raw_filename)
        ext = Path(safe_filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file format: {ext}. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        if self._retriever is None:
            raise RetrievalError("Retriever service not initialized.")

        upload_dir = self._get_upload_dir()
        target_path = upload_dir / safe_filename

        # Deduplication check: only skip if document actually exists in active vector store!
        active_docs = self._retriever.get_indexed_doc_names()
        active_docs_norm = {unicodedata.normalize("NFC", d) for d in active_docs}
        if safe_filename in active_docs_norm and target_path.exists():
            return safe_filename, target_path, True

        # Atomic file write: save to temporary file first, then rename to target_path.
        # The copy is bounded by MAX_UPLOAD_MB so a huge body cannot fill the disk.
        max_bytes = int(settings.max_upload_mb * 1024 * 1024)
        tmp_target = target_path.with_suffix(f"{ext}.tmp_{uuid.uuid4().hex[:8]}")
        try:
            written = 0
            with open(tmp_target, "wb") as f:
                while True:
                    buffer = fileobj.read(1024 * 1024)
                    if not buffer:
                        break
                    written += len(buffer)
                    if max_bytes and written > max_bytes:
                        raise UploadTooLargeError(
                            f"File '{filename}' exceeds the upload limit of {settings.max_upload_mb:g} MB."
                        )
                    f.write(buffer)
            os.replace(tmp_target, target_path)
        except Exception:
            tmp_target.unlink(missing_ok=True)
            raise

        return safe_filename, target_path, False

    def _process_stored_file(
        self, safe_filename: str, target_path: Path, original_filename: Optional[str]
    ) -> UploadResponse:
        """Extract, chunk, and index a stored upload; clean up on failure."""
        try:
            try:
                pages = extract_pages_from_document(str(target_path), ocr_engine=self._ocr_engine)
            except Exception as e:
                raise DocumentExtractionError(
                    f"Corrupted or unreadable document '{original_filename}': {e}"
                ) from e

            errors = [p["error"] for p in pages if p.get("error")]
            if errors and not any(p.get("text", "").strip() for p in pages):
                raise DocumentExtractionError(
                    f"Failed to extract text from '{original_filename}': {errors[0]}"
                )

            # Update doc_name to safe filename
            for p in pages:
                p["doc_name"] = safe_filename

            tokenizer = getattr(self._embedding_model, "tokenizer", None)
            max_tokens = get_chunk_token_limit(
                getattr(self._embedding_model, "max_seq_length", None),
                settings.chunk_size_tokens,
            )
            chunks = chunk_document(
                pages,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                tokenizer=tokenizer,
                max_tokens=max_tokens,
                overlap_tokens=settings.chunk_overlap_tokens,
            )
            try:
                indexed_count = self._retriever.index_chunks(chunks)
            except NotImplementedError as e:
                raise IndexingNotSupportedError(
                    "Document indexing is not supported by the active retrieval backend (e.g. gRPC mode)."
                ) from e

            scanned_count = sum(1 for p in pages if p.get("is_scanned"))
            digital_count = len(pages) - scanned_count

            return UploadResponse(
                filename=safe_filename,
                pages_extracted=len(pages),
                pages_digital=digital_count,
                pages_scanned_ocr=scanned_count,
                chunks_indexed=indexed_count,
                status="success"
            )
        except Exception:
            # If extraction or indexing failed, remove the unindexed file so corrupt files aren't kept
            target_path.unlink(missing_ok=True)
            raise

    def list_documents(self) -> List[FileSummary]:
        """List uploads that are actually indexed in the active vector store.

        Read-only: orphan files or transient upload temporaries are skipped,
        never deleted — cleanup belongs to a maintenance/reindex job.
        """
        upload_dir = self._get_upload_dir()

        active_docs = self._retriever.get_indexed_doc_names() if self._retriever is not None else set()
        active_docs_norm = {unicodedata.normalize("NFC", d) for d in active_docs}

        files: List[FileSummary] = []
        for f in sorted(upload_dir.iterdir(), key=lambda p: p.name.lower()):
            if f.is_file() and not f.name.startswith("."):
                norm_name = unicodedata.normalize("NFC", f.name)
                if norm_name not in active_docs_norm:
                    # Never delete from a GET request: a transient vector-store error
                    # or a collection rebuild must not wipe the raw uploads.
                    continue

                stat = f.stat()
                files.append(
                    FileSummary(
                        filename=norm_name,
                        size_bytes=stat.st_size,
                        uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        file_type=f.suffix.lower(),
                    )
                )
        return files

    def find_document_path(self, filename: str) -> Path:
        """Resolve a stored document to a safe on-disk path for serving.

        Raises :class:`NotFoundError` for path-traversal attempts, unknown
        names, and anything escaping the upload directory.
        """
        raw_name = Path(filename).name
        if not raw_name or raw_name in {".", ".."}:
            raise NotFoundError("File not found")

        safe_filename = unicodedata.normalize("NFC", raw_name)
        upload_dir = self._get_upload_dir()
        file_path = (upload_dir / safe_filename).resolve()

        if not file_path.is_file():
            file_path = None
            for cand in upload_dir.iterdir():
                if cand.is_file() and unicodedata.normalize("NFC", cand.name) == safe_filename:
                    file_path = cand.resolve()
                    break

        if file_path is None or not file_path.is_file() or not file_path.is_relative_to(upload_dir.resolve()):
            raise NotFoundError("File not found")
        return file_path

    def delete_document(self, filename: str) -> Dict[str, Any]:
        """Delete a document everywhere: vectors, BM25, and the stored file."""
        raw_name = Path(filename).name
        safe_filename = unicodedata.normalize("NFC", raw_name)

        file_path = self._resolve_file(safe_filename)

        deleted_chunks = 0
        if self._retriever is not None:
            deleted_chunks = self._retriever.delete_by_doc_name(safe_filename)

        file_existed = file_path is not None
        if file_path is not None:
            file_path.unlink(missing_ok=True)

        return {
            "status": "success",
            "filename": safe_filename,
            "file_deleted": file_existed,
            "chunks_removed": deleted_chunks,
            "message": f"Đã xoá hoàn toàn tài liệu '{safe_filename}' khỏi hệ thống."
        }


__all__ = ["IngestionService", "SUPPORTED_EXTENSIONS"]
