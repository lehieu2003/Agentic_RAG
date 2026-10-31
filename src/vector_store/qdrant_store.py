"""Qdrant vector store integration supporting local embedded mode."""

import uuid
from pathlib import Path
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from src.models import DocumentChunk, RetrievalResult


class QdrantVectorStore:
    """Vector database wrapper using Qdrant supporting both local embedded and cloud modes."""

    def __init__(
        self,
        storage_path: Optional[str] = "data/qdrant_storage",
        collection_name: str = "technical_documents",
        vector_size: int = 384,
        url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.storage_path = storage_path
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.url = url
        self.api_key = api_key

        if url:
            try:
                self.client = QdrantClient(url=url, api_key=api_key, timeout=60.0)
                self._ensure_collection()
                return
            except Exception as e:
                import logging
                logging.getLogger("qdrant_store").warning(
                    "Failed to connect to Qdrant Cloud (%s). Falling back to local embedded storage at '%s'.",
                    e, storage_path
                )
                self.url = None
                self.api_key = None

        if storage_path == ":memory:":
            self.client = QdrantClient(location=":memory:")
        else:
            local_path = storage_path or "data/qdrant_storage"
            Path(local_path).mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=local_path)

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create the collection if it does not exist."""
        try:
            existing = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in existing:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
        except Exception:
            pass

    def get_indexed_doc_names(self) -> set:
        """Return the set of distinct document names currently indexed."""
        self._ensure_collection()
        try:
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000,
                with_payload=True
            )
            doc_names = set()
            for p in points:
                if p.payload and p.payload.get("doc_name"):
                    doc_names.add(p.payload["doc_name"])
            return doc_names
        except Exception:
            return set()

    def delete_by_doc_name(self, doc_name: str) -> int:
        """Delete all vectors and payload matching doc_name."""
        self._ensure_collection()
        from qdrant_client.http import models
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_name",
                            match=models.MatchValue(value=doc_name)
                        )
                    ]
                )
            )
            return 1
        except Exception:
            return 0

    def upsert_chunks_with_vectors(
        self,
        chunks: List[DocumentChunk],
        vectors: List[List[float]]
    ) -> int:
        """Insert or update chunks along with precomputed vectors."""
        if not chunks:
            return 0
        self._ensure_collection()

        points: List[PointStruct] = []
        for chunk, vector in zip(chunks, vectors):
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            payload = {
                "chunk_id": chunk.chunk_id,
                "doc_name": chunk.doc_name,
                "page_number": chunk.page_number,
                "text": chunk.text,
                "metadata": chunk.metadata
            }
            points.append(PointStruct(id=point_uuid, vector=vector, payload=payload))

        batch_size = 100
        for i in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[i:i + batch_size]
            )
        return len(points)

    def search(self, query_vector: List[float], top_k: int = 5) -> List[RetrievalResult]:
        """Perform semantic search for nearest document chunks."""
        self._ensure_collection()
        try:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                with_payload=True
            )
        except Exception:
            return []

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

    def close(self) -> None:
        """Release underlying client file lock and resources."""
        if hasattr(self, "client") and self.client is not None:
            self.client.close()
