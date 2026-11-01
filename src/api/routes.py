"""API route definitions for Document Q&A Assistant."""

from datetime import datetime, timezone
import mimetypes
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List
import unicodedata
import uuid
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from src.config import settings
from src.ingestion.chunker import chunk_document
from src.ingestion.document_extractor import extract_pages_from_document
from src.models import FileSummary, QARequest, QAResponse, UploadResponse
from src.rag.agent import AgenticRAG

router = APIRouter(prefix="/api/v1")

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}


def _get_upload_dir() -> Path:
    """Ensure and return the upload directory path from settings."""
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


@router.get(
    "/health",
    tags=["Hệ thống (System)"],
    summary="Kiểm tra trạng thái hoạt động của hệ thống"
)
def health(request: Request) -> Dict[str, Any]:
    """Health check endpoint returning system status."""
    vstore = getattr(request.app.state, "vector_store", None)
    vector_mode = "cloud" if getattr(vstore, "url", None) else "local"
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "retrieval_mode": settings.retrieval_mode,
        "vector_store": vector_mode,
    }


@router.post(
    "/upload",
    response_model=UploadResponse,
    tags=["Tải lên tài liệu (Ingestion)"],
    summary="Tải lên tài liệu kỹ thuật để bóc tách text/OCR và đánh chỉ mục vector"
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...)
) -> UploadResponse:
    """Tải lên tài liệu kỹ thuật (PDF, DOCX, TXT, PNG, JPG, JPEG). Hệ thống sẽ:
    1. Kiểm tra định dạng hỗ trợ.
    2. Chống nạp trùng lặp dựa trên tên file trong thư mục lưu trữ.
    3. Lưu trữ file gốc vĩnh viễn vào data/uploads/.
    4. Trích xuất text kỹ thuật số hoặc OCR tuỳ định dạng.
    5. Phân đoạn ngữ nghĩa (chunking) bảo toàn số trang.
    6. Sinh embedding và lưu trữ vào Qdrant.
    """
    raw_filename = Path(file.filename).name if file.filename else "uploaded_document"
    safe_filename = unicodedata.normalize("NFC", raw_filename)
    ext = Path(safe_filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    upload_dir = _get_upload_dir()
    target_path = upload_dir / safe_filename

    retriever = getattr(request.app.state, "retriever", None)
    ocr_engine = getattr(request.app.state, "ocr_engine", None)

    if retriever is None:
        raise HTTPException(status_code=503, detail="Retriever service not initialized.")

    # Deduplication check: only skip if document actually exists in active vector store!
    active_docs = set()
    if hasattr(retriever, "get_indexed_doc_names"):
        active_docs = retriever.get_indexed_doc_names()

    active_docs_norm = {unicodedata.normalize("NFC", d) for d in active_docs}

    if safe_filename in active_docs_norm and target_path.exists():
        return UploadResponse(
            filename=safe_filename,
            pages_extracted=0,
            pages_digital=0,
            pages_scanned_ocr=0,
            chunks_indexed=0,
            status="already_exists",
            message=f"Tài liệu '{safe_filename}' đã tồn tại trên hệ thống. Bỏ qua nạp trùng lặp."
        )

    # Atomic file write: save to temporary file first, then rename to target_path
    tmp_target = target_path.with_suffix(f"{ext}.tmp_{uuid.uuid4().hex[:8]}")
    try:
        with open(tmp_target, "wb") as f:
            shutil.copyfileobj(file.file, f)
        os.replace(tmp_target, target_path)
    except Exception:
        tmp_target.unlink(missing_ok=True)
        raise

    try:
        try:
            pages = extract_pages_from_document(str(target_path), ocr_engine=ocr_engine)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Corrupted or unreadable document '{file.filename}': {e}")

        errors = [p["error"] for p in pages if p.get("error")]
        if errors and not any(p.get("text", "").strip() for p in pages):
            raise HTTPException(
                status_code=400,
                detail=f"Failed to extract text from '{file.filename}': {errors[0]}"
            )

        # Update doc_name to safe filename
        for p in pages:
            p["doc_name"] = safe_filename

        chunks = chunk_document(pages, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
        try:
            indexed_count = retriever.index_chunks(chunks)
        except NotImplementedError:
            raise HTTPException(
                status_code=501,
                detail="Document indexing is not supported by the active retrieval backend (e.g. gRPC mode)."
            )

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


@router.get(
    "/files",
    response_model=List[FileSummary],
    tags=["Quản lý tài liệu (Files)"],
    summary="Danh sách tất cả các tài liệu đã được lưu trữ vĩnh viễn"
)
def list_files(request: Request) -> List[FileSummary]:
    """Liệt kê danh sách tài liệu đang thực sự được đánh chỉ mục trong hệ thống.
    Đồng bộ với Qdrant Vector Store: nếu collection bị xoá hoặc rỗng, các file mồ côi
    trên ổ cứng sẽ tự động được dọn dẹp để đảm bảo tính nhất quán tuyệt đối.
    """
    upload_dir = _get_upload_dir()
    retriever = getattr(request.app.state, "retriever", None)

    active_docs = set()
    if retriever is not None and hasattr(retriever, "get_indexed_doc_names"):
        active_docs = retriever.get_indexed_doc_names()

    active_docs_norm = {unicodedata.normalize("NFC", d) for d in active_docs}

    files: List[FileSummary] = []
    for f in sorted(upload_dir.iterdir(), key=lambda p: p.name.lower()):
        if f.is_file() and not f.name.startswith("."):
            norm_name = unicodedata.normalize("NFC", f.name)
            if norm_name not in active_docs_norm:
                f.unlink(missing_ok=True)
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


@router.api_route(
    "/files/{filename:path}",
    methods=["GET", "HEAD"],
    tags=["Quản lý tài liệu (Files)"],
    summary="Tải hoặc xem trực tiếp tài liệu gốc trên trình duyệt"
)
async def serve_file(filename: str):
    """Phục vụ file tài liệu gốc để xem trực tiếp trên tab trình duyệt (hỗ trợ #page=N cho PDF)."""
    raw_name = Path(filename).name
    if not raw_name or raw_name in {".", ".."}:
        raise HTTPException(status_code=404, detail="File not found")

    safe_filename = unicodedata.normalize("NFC", raw_name)
    upload_dir = _get_upload_dir()
    file_path = (upload_dir / safe_filename).resolve()

    if not file_path.is_file():
        for cand in upload_dir.iterdir():
            if cand.is_file() and unicodedata.normalize("NFC", cand.name) == safe_filename:
                file_path = cand.resolve()
                break

    if not file_path.is_file() or not file_path.is_relative_to(upload_dir.resolve()):
        raise HTTPException(status_code=404, detail="File not found")

    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        filename=safe_filename,
        content_disposition_type="inline"
    )


@router.delete(
    "/files/{filename:path}",
    tags=["Quản lý tài liệu (Files)"],
    summary="Xoá tài liệu khỏi hệ thống và vector database"
)
def delete_document(request: Request, filename: str) -> Dict[str, Any]:
    """Xoá hoàn toàn tài liệu:
    1. Xoá tất cả vector và chunk trong Qdrant.
    2. Xoá chunk trong BM25.
    3. Xoá file vật lý trong data/uploads/.
    """
    raw_name = Path(filename).name
    if not raw_name or raw_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")

    safe_filename = unicodedata.normalize("NFC", raw_name)
    upload_dir = _get_upload_dir()
    file_path = upload_dir / safe_filename

    if not file_path.is_file():
        for cand in upload_dir.iterdir():
            if cand.is_file() and unicodedata.normalize("NFC", cand.name) == safe_filename:
                file_path = cand
                break

    retriever = getattr(request.app.state, "retriever", None)
    deleted_chunks = 0
    if retriever is not None and hasattr(retriever, "delete_by_doc_name"):
        deleted_chunks = retriever.delete_by_doc_name(safe_filename)

    file_existed = file_path.is_file()
    if file_existed:
        file_path.unlink(missing_ok=True)

    return {
        "status": "success",
        "filename": safe_filename,
        "file_deleted": file_existed,
        "chunks_removed": deleted_chunks,
        "message": f"Đã xoá hoàn toàn tài liệu '{safe_filename}' khỏi hệ thống."
    }


@router.post(
    "/query",
    response_model=QAResponse,
    tags=["Hỏi đáp tài liệu (Q&A)"],
    summary="Đặt câu hỏi kỹ thuật về tài liệu đã đánh chỉ mục"
)
def query_assistant(
    request: Request,
    qa_request: QARequest
) -> QAResponse:
    """Truy vấn trợ lý hỏi đáp kỹ thuật. Hệ thống sẽ:
    1. Tìm kiếm top-k đoạn tài liệu liên quan nhất trên Qdrant bằng vector embedding.
    2. Gửi ngữ cảnh tới LLM (Google Gemini / OpenAI) để tổng hợp câu trả lời kèm trích dẫn nguồn: `[Tài liệu: ..., Trang ...]`.
    3. Tự động từ chối (Abstention) nếu câu hỏi không có căn cứ trong tài liệu.
    """
    retriever = getattr(request.app.state, "retriever", None)
    generator = getattr(request.app.state, "generator", None)
    agent_instance = getattr(request.app.state, "agent", None)

    if retriever is None or (generator is None and agent_instance is None):
        raise HTTPException(status_code=503, detail="RAG system not initialized.")

    if agent_instance is not None and getattr(agent_instance, "retriever", None) is retriever:
        agent = agent_instance
    else:
        llm_client = getattr(agent_instance, "llm_client", getattr(generator, "llm_client", None))
        provider = getattr(agent_instance, "provider", getattr(generator, "provider", settings.llm_provider))
        model_name = getattr(agent_instance, "model_name", getattr(generator, "model_name", settings.gemini_model))
        reranker = getattr(request.app.state, "reranker", None)

        agent = AgenticRAG(
            retriever=retriever,
            reranker=reranker,
            llm_client=llm_client,
            provider=provider,
            model_name=model_name,
            min_relevance_score=settings.min_relevance_score
        )

    try:
        response = agent.answer(qa_request.question, top_k=qa_request.top_k)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Retrieval failure: {str(e)}")

    return response
