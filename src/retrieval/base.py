"""Abstract BaseRetriever interface."""

from abc import ABC, abstractmethod
from typing import List
from src.models import DocumentChunk, RetrievalResult


class BaseRetriever(ABC):
    """Abstract interface defining document chunk retrieval operations."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """Search for top_k relevant DocumentChunks matching the query.

        Args:
            query: User's question or search query string.
            top_k: Number of chunks to retrieve.

        Returns:
            List of RetrievalResult instances ordered by relevance.
        """
        pass

    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Index a batch of document chunks into the retriever's backend.

        Default implementation may be overridden by subclasses supporting indexing.
        """
        raise NotImplementedError("Indexing not supported by this retriever implementation.")

