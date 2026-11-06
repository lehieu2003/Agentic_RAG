"""Chat session listing, inspection, and deletion routes."""

from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_session_service
from src.application.session_service import SessionService
from src.models import (
    BatchDeleteSessionsRequest,
    SessionDetailResponse,
    SessionListResponse,
)

router = APIRouter()


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    tags=["Hội thoại (Sessions)"],
    summary="Danh sách tất cả các phiên hội thoại"
)
def list_sessions(
    session_service: Annotated[SessionService, Depends(get_session_service)],
    limit: int = Query(default=50, ge=1, le=200, description="Số lượng phiên tối đa cần lấy"),
) -> SessionListResponse:
    """Liệt kê danh sách các phiên trò chuyện, sắp xếp theo thời gian cập nhật mới nhất."""
    return session_service.list_sessions(limit=limit)

@router.get(
    "/sessions/{session_id}",
    response_model=SessionDetailResponse,
    tags=["Hội thoại (Sessions)"],
    summary="Chi tiết phiên hội thoại và lịch sử tin nhắn"
)
def get_session_detail(
    session_id: str,
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionDetailResponse:
    """Lấy thông tin chi tiết phiên hội thoại kèm toàn bộ tin nhắn đã gửi."""
    return session_service.get_session_detail(session_id)

@router.delete(
    "/sessions/{session_id}",
    tags=["Hội thoại (Sessions)"],
    summary="Xoá phiên hội thoại và toàn bộ tin nhắn liên quan"
)
def delete_session(
    session_id: str,
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> Dict[str, Any]:
    """Xoá một phiên hội thoại khỏi cơ sở dữ liệu."""
    return session_service.delete_session(session_id)

@router.delete(
    "/sessions",
    tags=["Hội thoại (Sessions)"],
    summary="Xoá toàn bộ các phiên hội thoại và tin nhắn"
)
def delete_all_sessions(
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> Dict[str, Any]:
    """Xoá toàn bộ phiên trò chuyện khỏi cơ sở dữ liệu."""
    return session_service.delete_all_sessions()

@router.post(
    "/sessions/batch-delete",
    tags=["Hội thoại (Sessions)"],
    summary="Xoá nhiều phiên hội thoại theo danh sách ID"
)
def delete_sessions_batch(
    body: BatchDeleteSessionsRequest,
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> Dict[str, Any]:
    """Xoá danh sách các phiên trò chuyện được chỉ định."""
    return session_service.delete_sessions_batch(body.session_ids)
