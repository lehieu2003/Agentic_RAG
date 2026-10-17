"""Qdrant vector store integration supporting local embedded mode."""

import uuid
from pathlib import Path
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from src.models import DocumentChunk, RetrievalResult


class QdrantVectorStore:
    """Vector database wrapper using Qdrant in local embedded file mode."""

    def __init__(
        self,
        storage_path: str = "data/qdrant_storage",
        collection_name: str = "technical_documents",
        vector_size: int = 384
    ):
        self.storage_path = storage_path
        self.collection_name = collection_name
        self.vector_size = vector_size

        if storage_path == ":memory:":
            self.client = QdrantClient(location=":memory:")
        else:
            Path(storage_path).mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=storage_path)

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create the collection if it does not exist."""
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )

    def upsert_chunks_with_vectors(
        self,
        chunks: List[DocumentChunk],
        vectors: List[List[float]]
    ) -> int:
        """Insert or update chunks along with precomputed vectors.

        Args:
            chunks: List of DocumentChunk models.
            vectors: Precomputed embedding vectors matching chunks.

        Returns:
            Number of points successfully upserted.
        """
        if not chunks:
            return 0

        points: List[PointStruct] = []
        for chunk, vector in zip(chunks, vectors):
            # Qdrant requires UUID string or unsigned integer for point IDs
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            payload = {
                "chunk_id": chunk.chunk_id,
                "doc_name": chunk.doc_name,
                "page_number": chunk.page_number,
                "text": chunk.text,
                "metadata": chunk.metadata
            }
            points.append(PointStruct(id=point_uuid, vector=vector, payload=payload))

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        return len(points)

    def search(self, query_vector: List[float], top_k: int = 5) -> List[RetrievalResult]:
        """Perform semantic search for nearest document chunks.

        Args:
            query_vector: Embedding vector of the query.
            top_k: Number of nearest neighbors to return.

        Returns:
            List of RetrievalResult instances.
        """
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True
        )

        results: List[RetrievalResult] = []
        for scored_point in response.points:
            payload = scored_point.payload or {}
            chunk = DocumentChunk(
                chunk_id=payload.get("chunk_id", str(scored_point.id)),
                doc_name=payload.get("doc_name", "unknown"),
                page_number=int(payload.get("page_number", 1)),
                text=payload.get("text", ""),
                metadata=payload.get("metadata", {})
            )
            results.append(RetrievalResult(chunk=chunk, score=float(scored_point.score)))

        return results

