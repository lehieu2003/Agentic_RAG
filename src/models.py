"""Pydantic data models for Document Q&A Assistant."""

from typing import Any, Dict, List
from pydantic import BaseModel, Field


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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "Nhiệt độ tối đa cho phép của thân bơm là bao nhiêu độ?",
                    "top_k": 3
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

