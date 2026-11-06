"""Question-answering route backed by the Agentic RAG engine."""

from fastapi import APIRouter, HTTPException, Request

from src.api.dependencies import get_session_store
from src.config import settings
from src.models import QARequest, QAResponse
from src.rag.agent import AgenticRAG

router = APIRouter()


@router.post(
    "/query",
    response_model=QAResponse,
    tags=["Hỏi đáp tài liệu (Q&A)"],
    summary="Đặt câu hỏi kỹ thuật về tài liệu đã đánh chỉ mục"
)
def query_assistant(
    request: Request,
    qa_request: QARequest
) -> QAResponse:
    """Truy vấn trợ lý hỏi đáp kỹ thuật. Hệ thống sẽ:
    1. Quản lý phiên hội thoại và tải ngữ cảnh lịch sử hội thoại gần nhất.
    2. Contextualize câu hỏi hiện tại dựa trên lịch sử để truy vấn chính xác.
    3. Tìm kiếm top-k đoạn tài liệu liên quan nhất trên Qdrant & BM25 kết hợp Reranker.
    4. Gửi ngữ cảnh tới LLM để tổng hợp câu trả lời kèm trích dẫn nguồn: `[Tài liệu: ..., Trang ...]`.
    5. Lưu lại tin nhắn của người dùng và câu trả lời vào SessionStore.
    """
    retriever = getattr(request.app.state, "retriever", None)
    generator = getattr(request.app.state, "generator", None)
    agent_instance = getattr(request.app.state, "agent", None)

    if retriever is None or (generator is None and agent_instance is None):
        raise HTTPException(status_code=503, detail="RAG system not initialized.")

    if agent_instance is not None and getattr(agent_instance, "retriever", None) is retriever:
        agent = agent_instance
    else:
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

    # 1. Retrieve or initialize SessionStore
    session_store = get_session_store(request)

    # 2. Resolve or create session_id
    session_title = qa_request.question[:40].strip() or "Cuộc trò chuyện mới"
    req_session_id = (qa_request.session_id or "").strip()
    if req_session_id:
        existing = session_store.get_session(req_session_id)
        if existing:
            session_id = req_session_id
        else:
            session_id = session_store.create_session(session_id=req_session_id, title=session_title)
    else:
        session_id = session_store.create_session(title=session_title)

    # 3. Retrieve recent messages for context
    recent_messages = session_store.get_recent_messages(session_id, limit=10)

    # 4. Invoke agent with conversation history
    try:
        response = agent.answer(qa_request.question, top_k=qa_request.top_k or settings.rerank_top_k, history=recent_messages)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Retrieval failure: {str(e)}")

    # 5. Persist user and assistant messages into session store
    session_store.add_message(
        session_id=session_id,
        role="user",
        content=qa_request.question,
    )
    session_store.add_message(
        session_id=session_id,
        role="assistant",
        content=response.answer,
        standalone_question=response.standalone_question,
        citations=response.citations,
        reasoning_steps=response.reasoning_steps,
    )

    # 6. Ensure returned response includes session_id
    return response.model_copy(update={"session_id": session_id})
