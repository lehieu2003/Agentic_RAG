"""RAG pipeline module with prompt construction, citation parsing, and abstention guardrails."""

from src.rag.prompt import build_rag_prompt, ABSTAIN_PHRASE
from src.rag.generator import RAGGenerator

__all__ = ["build_rag_prompt", "ABSTAIN_PHRASE", "RAGGenerator"]

