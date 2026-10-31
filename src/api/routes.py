"""API route definitions for Document Q&A Assistant."""

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from src.config import settings
from src.ingestion.chunker import chunk_document
from src.ingestion.document_extractor import extract_pages_from_document
from src.models import QARequest, QAResponse

router = APIRouter(prefix="/api/v1")

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}


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
    tags=["Tải lên tài liệu (Ingestion)"],
    summary="Tải lên tài liệu kỹ thuật để bóc tách text/OCR và đánh chỉ mục vector"
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """Tải lên tài liệu kỹ thuật (PDF, DOCX, TXT, PNG, JPG, JPEG). Hệ thống sẽ:
    1. Trích xuất text kỹ thuật số hoặc OCR tuỳ định dạng.
    2. Phân đoạn ngữ nghĩa (chunking) bảo toàn số trang.
    3. Sinh embedding và lưu trữ vào Qdrant Cloud.
    """
    safe_filename = Path(file.filename).name if file.filename else "uploaded_document"
    ext = Path(safe_filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    retriever = getattr(request.app.state, "retriever", None)
    ocr_engine = getattr(request.app.state, "ocr_engine", None)

    if retriever is None:
        raise HTTPException(status_code=503, detail="Retriever service not initialized.")

    # Save uploaded file to temporary path
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        try:
            pages = extract_pages_from_document(tmp_path, ocr_engine=ocr_engine)
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

        chunks = chunk_document(pages)
        try:
            indexed_count = retriever.index_chunks(chunks)
        except NotImplementedError:
            raise HTTPException(
                status_code=501,
                detail="Document indexing is not supported by the active retrieval backend (e.g. gRPC mode)."
            )

        scanned_count = sum(1 for p in pages if p.get("is_scanned"))
        digital_count = len(pages) - scanned_count

        return {
            "filename": safe_filename,
            "pages_extracted": len(pages),
            "pages_digital": digital_count,
            "pages_scanned_ocr": scanned_count,
            "chunks_indexed": indexed_count,
            "status": "success"
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


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

    if retriever is None or generator is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized.")

    try:
        chunks = retriever.search(qa_request.question, top_k=qa_request.top_k)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Retrieval failure: {str(e)}")

    response = generator.generate_answer(qa_request.question, chunks)
    return response
