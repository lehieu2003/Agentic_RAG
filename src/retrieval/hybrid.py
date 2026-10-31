"""Hybrid retriever combining dense vector search and sparse BM25 retrieval via Reciprocal Rank Fusion."""

from collections import defaultdict
from typing import Dict, List, Optional, Set, Union
import logging

from src.models import DocumentChunk, RetrievalResult
from src.retrieval.base import BaseRetriever
from src.retrieval.bm25 import BM25Retriever

logger = logging.getLogger(__name__)


class HybridRetriever(BaseRetriever):
    """Hybrid retriever combining dense and sparse retrievers using Reciprocal Rank Fusion (RRF)."""

    def __init__(
        self,
        dense_retriever: BaseRetriever,
        sparse_retriever: Union[BaseRetriever, BM25Retriever],
        rrf_k: int = 60,
    ) -> None:
        """Initialize HybridRetriever with dense and sparse retriever components.

        Args:
            dense_retriever: Dense semantic vector retriever (e.g. LocalRetriever or GrpcRetriever).
            sparse_retriever: Sparse keyword retriever (e.g. BM25Retriever).
            rrf_k: Constant k for Reciprocal Rank Fusion smoothing (default: 60).
        """
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever
        self.rrf_k = rrf_k

    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Index a batch of document chunks into both dense and sparse backends.

        Args:
            chunks: List of DocumentChunk instances to index.

        Returns:
            Number of chunks successfully dispatched for indexing.
        """
        if not chunks:
            return 0

        self.dense_retriever.index_chunks(chunks)
        self.sparse_retriever.index_chunks(chunks)
        return len(chunks)

    def search(self, query: str, top_k: int = 20) -> List[RetrievalResult]:
        """Search for top_k relevant DocumentChunks across dense and sparse retrievers merged via RRF.

        Args:
            query: User's question or search query string.
            top_k: Number of combined chunks to retrieve.

        Returns:
            List of RetrievalResult instances sorted descending by RRF score.
        """
        if not query or not isinstance(query, str) or not query.strip() or top_k <= 0:
            return []

        dense_results = self.dense_retriever.search(query, top_k=top_k)
        sparse_results = self.sparse_retriever.search(query, top_k=top_k)

        return self.reciprocal_rank_fusion(
            rank_lists=[dense_results, sparse_results],
            rrf_k=self.rrf_k,
            top_k=top_k,
        )

    @staticmethod
    def reciprocal_rank_fusion(
        rank_lists: List[List[RetrievalResult]],
        rrf_k: int = 60,
        top_k: int = 20,
    ) -> List[RetrievalResult]:
        """Fuse multiple ranked lists of RetrievalResult using Reciprocal Rank Fusion.

        Formula:
            score(d) = sum_{m in rank_lists} (1.0 / (rrf_k + rank_m(d)))
            where rank_m(d) is 1-indexed.

        Args:
            rank_lists: List of ranking lists, each containing RetrievalResult instances.
            rrf_k: Smoothing parameter k (default: 60).
            top_k: Maximum number of merged results to return.

        Returns:
            List of merged RetrievalResult instances ordered descending by RRF score.
        """
        if not rank_lists or top_k <= 0:
            return []

        rrf_scores: Dict[str, float] = defaultdict(float)
        chunk_map: Dict[str, DocumentChunk] = {}

        for results in rank_lists:
            seen_in_current_list: Set[str] = set()
            for rank, item in enumerate(results, start=1):
                chunk_id = item.chunk.chunk_id
                if chunk_id in seen_in_current_list:
                    continue
                seen_in_current_list.add(chunk_id)

                rrf_scores[chunk_id] += 1.0 / (rrf_k + rank)
                if chunk_id not in chunk_map:
                    chunk_map[chunk_id] = item.chunk

        # Sort chunks descending by RRF score
        sorted_chunk_ids = sorted(
            rrf_scores.keys(),
            key=lambda cid: rrf_scores[cid],
            reverse=True,
        )

        return [
            RetrievalResult(chunk=chunk_map[cid], score=rrf_scores[cid])
            for cid in sorted_chunk_ids[:top_k]
        ]
