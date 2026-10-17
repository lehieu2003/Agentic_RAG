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

    question: str
    top_k: int = Field(default=5, ge=1, le=20)


class QAResponse(BaseModel):
    """Response returned by the Document Q&A Assistant."""

    answer: str
    citations: List[Citation] = Field(default_factory=list)
    abstained: bool = False
    retrieved_chunks: List[RetrievalResult] = Field(default_factory=list)

