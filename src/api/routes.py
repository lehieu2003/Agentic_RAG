"""API route definitions for Document Q&A Assistant."""

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from src.config import settings
from src.ingestion.chunker import chunk_document
from src.ingestion.pdf_extractor import extract_pages_from_pdf
from src.models import QARequest, QAResponse

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health(request: Request) -> Dict[str, Any]:
    """Health check endpoint returning system status."""
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "retrieval_mode": settings.retrieval_mode
    }


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """Upload a PDF document, extract text/OCR, chunk and index into vector store."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported.")

    retriever = getattr(request.app.state, "retriever", None)
    ocr_engine = getattr(request.app.state, "ocr_engine", None)

    if retriever is None:
        raise HTTPException(status_code=503, detail="Retriever service not initialized.")

    # Save uploaded file to temporary path
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        pages = extract_pages_from_pdf(tmp_path, ocr_engine=ocr_engine)
        # Update doc_name to original filename
        for p in pages:
            p["doc_name"] = file.filename

        chunks = chunk_document(pages)
        indexed_count = retriever.index_chunks(chunks)

        return {
            "filename": file.filename,
            "pages_extracted": len(pages),
            "chunks_indexed": indexed_count,
            "status": "success"
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/query", response_model=QAResponse)
def query_assistant(
    request: Request,
    qa_request: QARequest
) -> QAResponse:
    """Ask a question about the indexed technical documents."""
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

