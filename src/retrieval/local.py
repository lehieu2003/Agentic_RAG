"""Local in-process retriever implementation connecting EmbeddingModel with QdrantVectorStore."""

from typing import List
from src.models import DocumentChunk, RetrievalResult
from src.retrieval.base import BaseRetriever
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore


class LocalRetriever(BaseRetriever):
    """Retriever operating directly against local embedding and vector store instances."""

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        vector_store: QdrantVectorStore
    ):
        self.embedding_model = embedding_model
        self.vector_store = vector_store

    def search(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """Encode query and perform vector search in Qdrant."""
        if not query.strip():
            return []
        query_vector = self.embedding_model.embed_query(query)
        return self.vector_store.search(query_vector=query_vector, top_k=top_k)

    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Compute embeddings and store chunks into Qdrant."""
        if not chunks:
            return 0
        texts = [chunk.text for chunk in chunks]
        vectors = self.embedding_model.embed_texts(texts)
        return self.vector_store.upsert_chunks_with_vectors(chunks=chunks, vectors=vectors)

