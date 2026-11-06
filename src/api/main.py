"""FastAPI application entrypoint with lifespan dependency wiring."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from src.api.rate_limit import RateLimitMiddleware
from src.api.error_handlers import register_error_handlers
from src.api.routes import router
from src.config import settings
from src.ingestion.chunker import chunk_document
from src.ingestion.document_extractor import extract_pages_from_document
from src.ingestion.ocr_engine import OcrEngine
from src.ingestion.tokenization import get_chunk_token_limit
from src.models import DocumentChunk
from src.rag.generator import RAGGenerator
from src.rag.agent import AgenticRAG
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.local import LocalRetriever
from src.retrieval.reranker import CrossEncoderReranker
from src.storage.session_store import SessionStore
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore

logger = logging.getLogger(__name__)


def _scroll_all_points(client, collection_name: str, limit: int = 1000):
    """Yield every point in a collection by following the scroll offset cursor.

    Reading a single page (10k/20k points) silently dropped everything beyond
    it, which made documents disappear from ``/files`` and broke BM25 hydration.
    """
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            limit=limit,
            offset=offset,
            with_payload=True,
        )
        if not points:
            return
        yield from points
        if offset is None:
            return


def _chunks_from_points(points) -> List[DocumentChunk]:
    """Rebuild ``DocumentChunk`` objects from Qdrant payloads (text-bearing only)."""
    return [
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


def _seed_bm25_retriever(
    bm25_retriever: BM25Retriever,
    vector_store: QdrantVectorStore,
    ocr_engine: OcrEngine,
    embedding_model: EmbeddingModel,
    chunk_token_limit: int,
) -> bool:
    """Hydrate the BM25 index so restarts do not need a full re-ingestion.

    Tiers: the active vector store client, then the local on-disk storage,
    then re-extraction from raw uploads. Returns True when seeded from
    stored chunks.
    """
    # Tier 1: the active vector store client (cloud or local), hydrate instantly.
    try:
        points = list(_scroll_all_points(vector_store.client, settings.qdrant_collection))
        if points:
            bm25_retriever.index_chunks(_chunks_from_points(points))
            return True
    except Exception as e:
        logger.warning("BM25 seeding from the active vector store failed: %s", e)

    # Tier 2: local on-disk storage as a secondary instant hydration source.
    local_client = None
    try:
        local_client = QdrantClient(path=settings.qdrant_path)
        points = list(_scroll_all_points(local_client, settings.qdrant_collection))
        if points:
            bm25_retriever.index_chunks(_chunks_from_points(points))
            return True
    except Exception as e:
        logger.warning("BM25 seeding from local Qdrant storage failed: %s", e)
    finally:
        if local_client is not None:
            try:
                local_client.close()
            except Exception:
                pass

    # Tier 3: extract from raw uploads only if the vector store was completely empty.
    upload_dir = Path(settings.upload_dir)
    if upload_dir.exists():
        for file_path in sorted(upload_dir.iterdir(), key=lambda p: p.name.lower()):
            if file_path.is_file() and not file_path.name.startswith("."):
                try:
                    import unicodedata
                    pages = extract_pages_from_document(str(file_path), ocr_engine=ocr_engine)
                    nfc_doc_name = unicodedata.normalize("NFC", file_path.name)
                    for p in pages:
                        p["doc_name"] = nfc_doc_name
                    chunks = chunk_document(
                        pages,
                        chunk_size=settings.chunk_size,
                        chunk_overlap=settings.chunk_overlap,
                        tokenizer=embedding_model.tokenizer,
                        max_tokens=chunk_token_limit,
                        overlap_tokens=settings.chunk_overlap_tokens,
                    )
                    bm25_retriever.index_chunks(chunks)
                except Exception as e:
                    logger.warning("BM25 fallback re-extraction failed for '%s': %s", file_path.name, e)
    return False


def _cors_origins() -> List[str]:
    """Parse the comma-separated CORS allow-list from settings ("*" by default)."""
    origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
    return origins or ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on application startup and teardown on shutdown."""
    # 1. OCR Engine
    app.state.ocr_engine = OcrEngine()

    # 2. Vector Store & Embedding Model
    app.state.embedding_model = EmbeddingModel(
        settings.embedding_model,
        device=settings.embedding_device or None,
        max_seq_length=settings.embedding_max_seq_length,
        batch_size=settings.embedding_batch_size,
    )
    chunk_token_limit = get_chunk_token_limit(
        app.state.embedding_model.max_seq_length,
        settings.chunk_size_tokens,
    )
    app.state.vector_store = QdrantVectorStore(
        storage_path=settings.qdrant_path,
        collection_name=settings.qdrant_collection,
        vector_size=app.state.embedding_model.dimension,
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

    # Rebuild BM25 index: hydrate from the vector store (paginated), falling
    # back to local storage, then to re-extracting the raw uploads.
    _seed_bm25_retriever(
        bm25_retriever=bm25_retriever,
        vector_store=app.state.vector_store,
        ocr_engine=app.state.ocr_engine,
        embedding_model=app.state.embedding_model,
        chunk_token_limit=chunk_token_limit,
    )

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
        except Exception as e:
            logger.warning("Failed to initialize the Gemini client: %s", e)
            llm_client = None
    elif settings.llm_provider == "openai" and settings.openai_api_key:
        try:
            from openai import OpenAI
            llm_client = OpenAI(api_key=settings.openai_api_key)
        except Exception as e:
            logger.warning("Failed to initialize the OpenAI client: %s", e)
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

    # 5. Session Store for multi-turn conversation memory
    app.state.session_store = SessionStore(db_path=settings.session_db_path)

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
    allow_origins=_cors_origins(),
    # Credentials with a wildcard origin are invalid per the CORS spec and
    # every browser rejects it; the SPA is cookie-less, so credentials are
    # only meaningful with an explicit allow-list.
    allow_credentials=_cors_origins() != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Opt-in per-IP throttling (RATE_LIMIT_RPM, 0 = disabled).
app.add_middleware(RateLimitMiddleware, rpm=settings.rate_limit_rpm)

# Domain errors raised anywhere in the application map onto the HTTP
# {"detail": ...} contract at this single edge.
register_error_handlers(app)

app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    """Tự động chuyển hướng từ trang chủ sang Swagger UI."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
