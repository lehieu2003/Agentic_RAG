"""Question-answering routes backed by the Agentic RAG engine.

``/query`` returns the full answer in one JSON response; ``/query/stream``
sends the same turn as Server-Sent Events (session → reasoning steps →
answer → done) so the UI can show progress while the pipeline runs.
"""

import json
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.api.dependencies import get_chat_service
from src.application.chat_service import ChatService
from src.models import QARequest, QAResponse

router = APIRouter()


@router.post(
    "/query",
    response_model=QAResponse,
    tags=["Hỏi đáp tài liệu (Q&A)"],
    summary="Đặt câu hỏi kỹ thuật về tài liệu đã đánh chỉ mục"
)
def query_assistant(
    qa_request: QARequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> QAResponse:
    """Truy vấn trợ lý hỏi đáp kỹ thuật. Hệ thống sẽ:
    1. Quản lý phiên hội thoại và tải ngữ cảnh lịch sử hội thoại gần nhất.
    2. Contextualize câu hỏi hiện tại dựa trên lịch sử để truy vấn chính xác.
    3. Tìm kiếm top-k đoạn tài liệu liên quan nhất trên Qdrant & BM25 kết hợp Reranker.
    4. Gửi ngữ cảnh tới LLM để tổng hợp câu trả lời kèm trích dẫn nguồn: `[Tài liệu: ..., Trang ...]`.
    5. Lưu lại tin nhắn của người dùng và câu trả lời vào SessionStore.
    """
    return chat_service.answer(
        question=qa_request.question,
        top_k=qa_request.top_k,
        session_id=qa_request.session_id,
    )


_SSE_EVENT_NAMES = {
    "session": "session",
    "step": "reasoning",
    "answer": "answer",
    "error": "error",
    "done": "done",
}


def _format_sse(event: dict) -> str:
    """Render one service event as an SSE frame."""
    event_type = _SSE_EVENT_NAMES.get(event.get("type", ""), "message")
    payload = {k: v for k, v in event.items() if k != "type"}
    if event_type == "answer":
        payload = {"response": payload["response"].model_dump(mode="json")}
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post(
    "/query/stream",
    tags=["Hỏi đáp tài liệu (Q&A)"],
    summary="Đặt câu hỏi và nhận câu trả lời dạng stream (Server-Sent Events)",
)
def query_assistant_stream(
    qa_request: QARequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    """Cùng pipeline với `/query`, nhưng gửi từng bước suy luận ngay khi có:
    `session` → các event `reasoning` (mỗi node LangGraph hoàn thành) →
    `answer` (QAResponse đầy đủ) → `done`. Lỗi trả về event `error`.
    """
    events = chat_service.answer_stream(
        question=qa_request.question,
        top_k=qa_request.top_k,
        session_id=qa_request.session_id,
    )

    async def sse_response() -> AsyncIterator[str]:
        for event in events:
            yield _format_sse(event)

    return StreamingResponse(
        sse_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx response buffering
        },
    )
