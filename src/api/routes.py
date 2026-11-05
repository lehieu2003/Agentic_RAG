"""API route definitions for Document Q&A Assistant.

Endpoints are grouped by domain under ``src/api/routers`` and mounted on a
single versioned router so the public URL layout stays unchanged.
"""

from fastapi import APIRouter

from src.api.routers import documents, query, sessions, system

router = APIRouter(prefix="/api/v1")
router.include_router(system.router)
router.include_router(documents.router)
router.include_router(sessions.router)
router.include_router(query.router)

__all__ = ["router"]
