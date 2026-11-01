"""Pydantic data models for Document Q&A Assistant."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response returned upon document upload and indexing."""

    filename: str
    pages_extracted: int
    pages_digital: int
    pages_scanned_ocr: int
    chunks_indexed: int
    status: str = "success"
    message: Optional[str] = None


class FileSummary(BaseModel):
    """Summary metadata of an uploaded file stored on disk."""

    filename: str
    size_bytes: int
    uploaded_at: str
    file_type: str


class DocumentChunk(BaseModel):
    """Represents a chunk of text extracted from a specific document and page."""

    chunk_id: str
    doc_name: str
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """Result returned from vector similarity search."""

    chunk: DocumentChunk
    score: float = Field(..., description="Similarity score (e.g. Cosine distance/similarity)")


class Citation(BaseModel):
    """Citation referencing a specific document and page."""

    doc_name: str
    page_number: int = Field(..., ge=1)


class QARequest(BaseModel):
    """Incoming user question request."""

    question: str = Field(
        ...,
        description="Câu hỏi bằng ngôn ngữ tự nhiên về tài liệu kỹ thuật",
        examples=["Nhiệt độ tối đa cho phép của thân bơm là bao nhiêu độ?"]
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Số lượng đoạn văn bản liên quan nhất cần truy xuất từ Qdrant",
        examples=[3]
    )
    session_id: Optional[str] = Field(
        default=None,
        description="ID phiên hội thoại cho ngữ cảnh đa lượt (multi-turn conversation)",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "Nhiệt độ tối đa cho phép của thân bơm là bao nhiêu độ?",
                    "top_k": 3,
                    "session_id": "550e8400-e29b-41d4-a716-446655440000"
                }
            ]
        }
    }


class QAResponse(BaseModel):
    """Response returned by the Document Q&A Assistant."""

    answer: str
    citations: List[Citation] = Field(default_factory=list)
    abstained: bool = False
    retrieved_chunks: List[RetrievalResult] = Field(default_factory=list)
    rewritten_queries: Optional[List[str]] = None
    reasoning_steps: Optional[List[str]] = None
    standalone_question: Optional[str] = None
    session_id: Optional[str] = None


class SessionSummary(BaseModel):
    """Summary of a chat session."""

    id: str
    title: str
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    """List of all chat session summaries."""

    sessions: List[SessionSummary]


class ChatMessage(BaseModel):
    """Represents a single message in a conversation session."""

    role: str
    content: str
    citations: Optional[List[Citation]] = None
    reasoning_steps: Optional[List[str]] = None
    created_at: Optional[str] = None
    id: Optional[str] = None
    standalone_question: Optional[str] = None

    model_config = {"extra": "ignore"}


class SessionDetailResponse(BaseModel):
    """Detailed chat session including history messages."""

    session: SessionSummary
    messages: List[ChatMessage]


class BatchDeleteSessionsRequest(BaseModel):
    """Request payload to delete multiple chat sessions."""

    session_ids: List[str] = Field(default_factory=list, description="Danh sách ID các phiên cần xoá")

