"""System health routes."""

from typing import Any, Dict

from fastapi import APIRouter, Request

from src.config import settings

router = APIRouter()


@router.get(
    "/health",
    tags=["Hệ thống (System)"],
    summary="Kiểm tra trạng thái hoạt động của hệ thống"
)
def health(request: Request) -> Dict[str, Any]:
    """Health check endpoint returning system status."""
    vstore = getattr(request.app.state, "vector_store", None)
    vector_mode = "cloud" if getattr(vstore, "url", None) else "local"
    vector_count = None
    try:
        vector_count = vstore.client.count(collection_name=vstore.collection_name, exact=True).count
    except Exception:
        # Collection not created yet or store unreachable; health itself stays "ok".
        vector_count = None
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "retrieval_mode": settings.retrieval_mode,
        "vector_store": vector_mode,
        "vector_store_count": vector_count,
    }
