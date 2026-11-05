"""Execution state passed between nodes in the Agentic RAG graph."""

from typing import Dict, List, Optional, TypedDict

from src.models import Citation, RetrievalResult


class AgentState(TypedDict, total=False):
    """Execution state passed between nodes in the Agentic RAG v2 graph."""

    # Input queries & conversation context
    question: str                         # Raw user query
    clean_question: str                   # Cleaned query after removing greeting prefixes
    history: List[Dict[str, str]]         # Prior conversation messages
    standalone_question: str              # Contextualized / standalone query
    is_chitchat: bool                     # True if query is purely social/greeting
    chitchat_reply: Optional[str]         # Canned friendly response for greetings

    # Retrieval & Reranking
    queries: List[str]                    # Active queries for this iteration
    all_queries: List[str]                # Cumulative query history
    candidate_chunks: List[RetrievalResult]  # Candidates from RRF (top 20)
    reranked_chunks: List[RetrievalResult]   # Top reranked chunks (top 5)

    # Grading & Reflection
    is_sufficient: bool                   # True if chunks contain sufficient factual answers
    grader_feedback: str                  # Explanation of missing information if insufficient
    retries: int                          # Retrieval rewrite attempt counter (max 1)

    # Generation & Self-Correction
    gen_retries: int                      # Citation correction attempt counter (max 1)
    citation_feedback: Optional[str]      # Error description passed back to generator
    answer: str                           # Synthesized text
    citations: List[Citation]             # Validated citations
    abstained: bool                       # True if refusing to answer

    # Observability
    reasoning_steps: List[str]            # Step-by-step audit log for UI inspection

    # Graph flow auxiliary
    top_k: int
    raw_generation: str
    is_citation_valid: bool
    retry_generation: bool
    relevant_chunks: List[RetrievalResult]
    max_score: float
