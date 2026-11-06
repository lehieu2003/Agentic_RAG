"""Qdrant vector store integration supporting local embedded mode."""

import logging
import uuid
from pathlib import Path
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from src.models import DocumentChunk, RetrievalResult

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Vector database wrapper using Qdrant supporting both local embedded and cloud modes."""

    def __init__(
        self,
        storage_path: Optional[str] = "data/qdrant_storage",
        collection_name: str = "technical_documents",
        vector_size: int = 384,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        recreate: bool = False,
    ):
        self.storage_path = storage_path
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.url = url
        self.api_key = api_key
        self.recreate = recreate
        self._collection_ready = False

        if url:
            try:
                self.client = QdrantClient(url=url, api_key=api_key, timeout=60.0)
                if recreate:
                    self._delete_collection_if_exists()
                self._ensure_collection()
                return
            except ValueError:
                # A dimension mismatch must be surfaced instead of silently
                # falling back to a different local collection.
                raise
            except Exception as e:
                logger.warning(
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

        if recreate:
            self._delete_collection_if_exists()
        self._ensure_collection()

    def _delete_collection_if_exists(self) -> None:
        """Delete the configured collection when an explicit rebuild is requested."""
        try:
            existing = [c.name for c in self.client.get_collections().collections]
            if self.collection_name in existing:
                self.client.delete_collection(collection_name=self.collection_name)
        except Exception as e:
            logger.warning("Could not delete collection '%s' before rebuild: %s", self.collection_name, e)

    def _ensure_collection(self) -> None:
        """Create the collection if needed and fail fast on a dimension mismatch."""
        if self._collection_ready:
            return

        try:
            existing = [c.name for c in self.client.get_collections().collections]
        except Exception as e:
            logger.warning("Could not list Qdrant collections to verify readiness: %s", e)
            return

        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )
            self._collection_ready = True
            return

        try:
            info = self.client.get_collection(self.collection_name)
            vectors_config = getattr(getattr(info, "config", None), "params", None)
            vectors_config = getattr(vectors_config, "vectors", None)
            existing_size = getattr(vectors_config, "size", None)
            if existing_size is not None and int(existing_size) != int(self.vector_size):
                raise ValueError(
                    f"Qdrant collection '{self.collection_name}' has vector size "
                    f"{existing_size}, but the configured embedding model produces "
                    f"{self.vector_size} dimensions. Re-create the collection and "
                    f"reindex: python scripts/reindex.py --recreate --yes"
                )
        except ValueError:
            raise
        except Exception:
            # Some Qdrant-compatible backends do not expose collection metadata;
            # keep the previous permissive behavior in that case.
            pass

        self._collection_ready = True

    def get_indexed_doc_names(self) -> set:
        """Return the set of distinct document names currently indexed.

        Scrolls with the offset cursor so collections beyond a single page
        (10k+ chunks previously) are fully covered, and fetches only the
        ``doc_name`` payload field.
        """
        self._ensure_collection()
        doc_names: set = set()
        try:
            offset = None
            while True:
                points, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    offset=offset,
                    with_payload=["doc_name"],
                )
                for p in points:
                    if p.payload and p.payload.get("doc_name"):
                        doc_names.add(p.payload["doc_name"])
                if offset is None:
                    break
            return doc_names
        except Exception as e:
            logger.warning("Failed to list indexed documents from Qdrant: %s", e)
            return doc_names

    def delete_by_doc_name(self, doc_name: str) -> int:
        """Delete all vectors and payload matching doc_name (in both NFC and NFD forms)."""
        self._ensure_collection()
        from qdrant_client.http import models
        import unicodedata
        nfc_name = unicodedata.normalize("NFC", doc_name)
        nfd_name = unicodedata.normalize("NFD", doc_name)
        values = list({doc_name, nfc_name, nfd_name})
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.Filter(
                    should=[
                        models.FieldCondition(
                            key="doc_name",
                            match=models.MatchValue(value=v)
                        )
                        for v in values
                    ]
                )
            )
            return 1
        except Exception as e:
            logger.warning("Failed to delete vectors for document '%s': %s", doc_name, e)
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
        import unicodedata

        points: List[PointStruct] = []
        for chunk, vector in zip(chunks, vectors):
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            norm_doc_name = unicodedata.normalize("NFC", chunk.doc_name)
            payload = {
                "chunk_id": chunk.chunk_id,
                "doc_name": norm_doc_name,
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
        except Exception as e:
            logger.warning("Vector search failed, returning no results: %s", e)
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
