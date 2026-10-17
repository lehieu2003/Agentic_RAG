"""FastAPI application entrypoint with lifespan dependency wiring."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router
from src.config import settings
from src.ingestion.ocr_engine import OcrEngine
from src.rag.generator import RAGGenerator
from src.retrieval.local import LocalRetriever
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

    # 3. Retriever initialization
    if settings.retrieval_mode == "grpc":
        from src.retrieval.grpc_client import GrpcRetriever
        app.state.retriever = GrpcRetriever(
            host=settings.grpc_host,
            port=settings.grpc_port
        )
    else:
        app.state.retriever = LocalRetriever(
            embedding_model=app.state.embedding_model,
            vector_store=app.state.vector_store
        )

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

    app.state.generator = RAGGenerator(
        llm_client=llm_client,
        provider=settings.llm_provider
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
