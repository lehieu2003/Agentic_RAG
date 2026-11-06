"""Question-answering route backed by the Agentic RAG engine."""

from typing import Annotated

from fastapi import APIRouter, Depends

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
