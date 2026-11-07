"""Typed FastAPI dependency providers — the request-scoped composition root.

This module is the single place that resolves collaborators from
``app.state`` (wired once in the lifespan). Routers depend on typed
application services via ``Depends`` and never reach into app state, or
into ``src.config.settings``, themselves.
"""

from fastapi import HTTPException, Request

from src.application.chat_service import ChatService
from src.application.ingestion_jobs import IngestionJobStore
from src.application.ingestion_service import IngestionService
from src.application.session_service import SessionService
from src.config import settings
from src.rag.agent import AgenticRAG
from src.storage.session_store import SessionStore


def verify_api_key(request: Request) -> None:
    """Opt-in API-key gate for business routes (no-op while ``API_KEY`` is unset).

    Accepts either an ``X-API-Key`` header or an ``Authorization: Bearer <key>``
    header so command-line clients work without special tooling.
    """
    expected = settings.api_key
    if not expected:
        return

    provided = request.headers.get("X-API-Key") or ""
    if not provided:
        auth = request.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            provided = auth[len("Bearer "):]

    import secrets
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


def get_session_store(request: Request) -> SessionStore:
    """Return the app-level session store, creating it on first use."""
    session_store = getattr(request.app.state, "session_store", None)
    if session_store is None:
        session_store = SessionStore(db_path=settings.session_db_path)
        request.app.state.session_store = session_store
    return session_store


def get_chat_service(request: Request) -> ChatService:
    """Assemble the chat use-case from the wired RAG collaborators."""
    retriever = getattr(request.app.state, "retriever", None)
    generator = getattr(request.app.state, "generator", None)
    agent_instance = getattr(request.app.state, "agent", None)

    if retriever is None or (generator is None and agent_instance is None):
        raise HTTPException(status_code=503, detail="RAG system not initialized.")

    if agent_instance is not None and getattr(agent_instance, "retriever", None) is retriever:
        agent = agent_instance
    else:
        # Hot-swapped retriever (ops tooling / tests): rebuild the agent
        # around the retriever currently installed on app.state.
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

    return ChatService(
        agent=agent,
        session_store=get_session_store(request),
        default_top_k=settings.rerank_top_k,
    )


def get_ingestion_service(request: Request) -> IngestionService:
    """Assemble the document-ingestion use-case from the wired collaborators."""
    return IngestionService(
        retriever=getattr(request.app.state, "retriever", None),
        ocr_engine=getattr(request.app.state, "ocr_engine", None),
        embedding_model=getattr(request.app.state, "embedding_model", None),
    )


def get_ingestion_job_store(request: Request) -> IngestionJobStore:
    """Return the app-level ingestion job registry, creating it on first use."""
    job_store = getattr(request.app.state, "ingestion_job_store", None)
    if job_store is None:
        job_store = IngestionJobStore()
        request.app.state.ingestion_job_store = job_store
    return job_store


def get_session_service(request: Request) -> SessionService:
    """Assemble the session-management use-case."""
    return SessionService(session_store=get_session_store(request))
