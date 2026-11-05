"""Chat session listing, inspection, and deletion routes."""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.dependencies import get_session_store
from src.models import (
    BatchDeleteSessionsRequest,
    ChatMessage,
    SessionDetailResponse,
    SessionListResponse,
    SessionSummary,
)

router = APIRouter()


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    tags=["Hội thoại (Sessions)"],
    summary="Danh sách tất cả các phiên hội thoại"
)
def list_sessions(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="Số lượng phiên tối đa cần lấy"),
) -> SessionListResponse:
    """Liệt kê danh sách các phiên trò chuyện, sắp xếp theo thời gian cập nhật mới nhất."""
    session_store = get_session_store(request)

    sessions_raw = session_store.list_sessions(limit=limit)
    sessions = [
        SessionSummary(
            id=s["id"],
            title=s["title"],
            created_at=str(s["created_at"]),
            updated_at=str(s["updated_at"]),
        )
        for s in sessions_raw
    ]
    return SessionListResponse(sessions=sessions)

@router.get(
    "/sessions/{session_id}",
    response_model=SessionDetailResponse,
    tags=["Hội thoại (Sessions)"],
    summary="Chi tiết phiên hội thoại và lịch sử tin nhắn"
)
def get_session_detail(request: Request, session_id: str) -> SessionDetailResponse:
    """Lấy thông tin chi tiết phiên hội thoại kèm toàn bộ tin nhắn đã gửi."""
    session_store = get_session_store(request)

    sess_raw = session_store.get_session(session_id)
    if not sess_raw:
        raise HTTPException(status_code=404, detail="Session not found")

    messages_raw = session_store.get_messages(session_id)
    messages = [ChatMessage(**m) for m in messages_raw]
    return SessionDetailResponse(
        session=SessionSummary(**sess_raw),
        messages=messages,
    )

@router.delete(
    "/sessions/{session_id}",
    tags=["Hội thoại (Sessions)"],
    summary="Xoá phiên hội thoại và toàn bộ tin nhắn liên quan"
)
def delete_session(request: Request, session_id: str) -> Dict[str, Any]:
    """Xoá một phiên hội thoại khỏi cơ sở dữ liệu."""
    session_store = get_session_store(request)

    deleted = session_store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "status": "success",
        "session_id": session_id,
        "message": f"Đã xoá phiên hội thoại '{session_id}' thành công."
    }

@router.delete(
    "/sessions",
    tags=["Hội thoại (Sessions)"],
    summary="Xoá toàn bộ các phiên hội thoại và tin nhắn"
)
def delete_all_sessions(request: Request) -> Dict[str, Any]:
    """Xoá toàn bộ phiên trò chuyện khỏi cơ sở dữ liệu."""
    session_store = get_session_store(request)

    deleted_count = session_store.delete_all_sessions()
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "message": f"Đã xoá toàn bộ {deleted_count} phiên hội thoại thành công."
    }

@router.post(
    "/sessions/batch-delete",
    tags=["Hội thoại (Sessions)"],
    summary="Xoá nhiều phiên hội thoại theo danh sách ID"
)
def delete_sessions_batch(request: Request, body: BatchDeleteSessionsRequest) -> Dict[str, Any]:
    """Xoá danh sách các phiên trò chuyện được chỉ định."""
    session_store = get_session_store(request)

    deleted_count = session_store.delete_sessions(body.session_ids)
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "message": f"Đã xoá {deleted_count} phiên hội thoại thành công."
    }
