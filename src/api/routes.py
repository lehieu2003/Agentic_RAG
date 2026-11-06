"""API route definitions for Document Q&A Assistant.

Endpoints are grouped by domain under ``src/api/routers`` and mounted on a
single versioned router so the public URL layout stays unchanged. The
opt-in API-key gate covers the business routers; ``/health`` stays open
for orchestrator probes.
"""

from fastapi import APIRouter, Depends

from src.api.dependencies import verify_api_key
from src.api.routers import documents, query, sessions, system

router = APIRouter(prefix="/api/v1")
router.include_router(system.router)
router.include_router(documents.router, dependencies=[Depends(verify_api_key)])
router.include_router(sessions.router, dependencies=[Depends(verify_api_key)])
router.include_router(query.router, dependencies=[Depends(verify_api_key)])

__all__ = ["router"]
