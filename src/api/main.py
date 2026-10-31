"""FastAPI application entrypoint with lifespan dependency wiring."""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router
from src.config import settings
from src.ingestion.chunker import chunk_document
from src.ingestion.document_extractor import extract_pages_from_document
from src.ingestion.ocr_engine import OcrEngine
from src.rag.generator import RAGGenerator
from src.rag.agent import AgenticRAG
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.local import LocalRetriever
from src.retrieval.reranker import CrossEncoderReranker
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on application startup and teardown on shutdown."""
    # 1. OCR Engine
    app.state.ocr_engine = OcrEngine()

    # 2. Vector Store & Embedding Model
    app.state.embedding_model = EmbeddingModel(settings.embedding_model)
    app.state.vector_store = QdrantVectorStore(
        storage_path=settings.qdrant_path,
        collection_name=settings.qdrant_collection,
        url=settings.qdrant_url if settings.qdrant_url else None,
        api_key=settings.qdrant_api_key if settings.qdrant_api_key else None
    )

    # 3. Dense & Sparse Hybrid Retriever initialization
    if settings.retrieval_mode == "grpc":
        from src.retrieval.grpc_client import GrpcRetriever
        dense_retriever = GrpcRetriever(
            host=settings.grpc_host,
            port=settings.grpc_port
        )
    else:
        dense_retriever = LocalRetriever(
            embedding_model=app.state.embedding_model,
            vector_store=app.state.vector_store
        )
    app.state.dense_retriever = dense_retriever

    # Sparse BM25 Retriever
    bm25_retriever = BM25Retriever()
    app.state.bm25_retriever = bm25_retriever

    # Rebuild BM25 index: hydrate instantly from vector_store points (<0.05s) if available
    seeded = False
    if hasattr(app.state.vector_store, "client"):
        try:
            points, _ = app.state.vector_store.client.scroll(
                collection_name=settings.qdrant_collection,
                limit=20000,
                with_payload=True
            )
            if points:
                from src.models import DocumentChunk
                chunks_from_store = [
                    DocumentChunk(
                        chunk_id=p.payload.get("chunk_id", str(p.id)),
                        doc_name=p.payload.get("doc_name", "unknown"),
                        page_number=int(p.payload.get("page_number", 1)),
                        text=p.payload.get("text", ""),
                        metadata=p.payload.get("metadata", {})
                    )
                    for p in points
                    if p.payload and p.payload.get("text")
                ]
                bm25_retriever.index_chunks(chunks_from_store)
                seeded = True
        except Exception:
            seeded = False

    # Check local on-disk storage as secondary instant hydration source
    if not seeded:
        try:
            from qdrant_client import QdrantClient
            local_client = QdrantClient(path=settings.qdrant_path)
            local_points, _ = local_client.scroll(
                collection_name=settings.qdrant_collection,
                limit=20000,
                with_payload=True
            )
            if local_points:
                from src.models import DocumentChunk
                chunks_from_store = [
                    DocumentChunk(
                        chunk_id=p.payload.get("chunk_id", str(p.id)),
                        doc_name=p.payload.get("doc_name", "unknown"),
                        page_number=int(p.payload.get("page_number", 1)),
                        text=p.payload.get("text", ""),
                        metadata=p.payload.get("metadata", {})
                    )
                    for p in local_points
                    if p.payload and p.payload.get("text")
                ]
                bm25_retriever.index_chunks(chunks_from_store)
                seeded = True
            local_client.close()
        except Exception:
            pass

    # Fallback: extract from raw uploads only if vector store was completely empty
    if not seeded:
        upload_dir = Path(settings.upload_dir)
        if upload_dir.exists():
            for file_path in sorted(upload_dir.iterdir(), key=lambda p: p.name.lower()):
                if file_path.is_file() and not file_path.name.startswith("."):
                    try:
                        import unicodedata
                        pages = extract_pages_from_document(str(file_path), ocr_engine=app.state.ocr_engine)
                        nfc_doc_name = unicodedata.normalize("NFC", file_path.name)
                        for p in pages:
                            p["doc_name"] = nfc_doc_name
                        chunks = chunk_document(pages, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
                        bm25_retriever.index_chunks(chunks)
                    except Exception:
                        pass

    # Hybrid Retriever combining dense and sparse via RRF
    hybrid_retriever = HybridRetriever(
        dense_retriever=dense_retriever,
        sparse_retriever=bm25_retriever,
        rrf_k=settings.hybrid_rrf_k
    )
    app.state.retriever = hybrid_retriever

    # Cross-Encoder Reranker
    reranker = CrossEncoderReranker(model_name=settings.reranker_model)
    app.state.reranker = reranker

    # 4. LLM client & RAG Generator
    llm_client = None
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        try:
            from google import genai
            llm_client = genai.Client(api_key=settings.gemini_api_key)
        except Exception:
            llm_client = None
    elif settings.llm_provider == "openai" and settings.openai_api_key:
        try:
            from openai import OpenAI
            llm_client = OpenAI(api_key=settings.openai_api_key)
        except Exception:
            llm_client = None

    active_model = settings.gemini_model if settings.llm_provider == "gemini" else None
    app.state.generator = RAGGenerator(
        llm_client=llm_client,
        provider=settings.llm_provider,
        model_name=active_model,
        min_relevance_score=settings.min_relevance_score
    )
    app.state.agent = AgenticRAG(
        retriever=app.state.retriever,
        reranker=app.state.reranker,
        llm_client=llm_client,
        provider=settings.llm_provider,
        model_name=active_model,
        min_relevance_score=settings.min_relevance_score
    )

    try:
        yield
    finally:
        # Proper resource cleanup
        if hasattr(app.state, "vector_store") and app.state.vector_store is not None:
            try:
                app.state.vector_store.close()
            except Exception:
                pass


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Document Q&A Assistant - Hỏi đáp tài liệu kỹ thuật có trích dẫn nguồn và abstention guardrail",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    """Tự động chuyển hướng từ trang chủ sang Swagger UI."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
