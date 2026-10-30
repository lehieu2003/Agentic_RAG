# tests/test_vector_store.py
import pytest
from pathlib import Path
from src.models import DocumentChunk
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore

@pytest.fixture
def temp_qdrant_store(tmp_path: Path):
    embedder = EmbeddingModel(model_name="all-MiniLM-L6-v2")
    store = QdrantVectorStore(storage_path=str(tmp_path / "qdrant"), collection_name="test_collection")
    return embedder, store

def test_embed_and_search(temp_qdrant_store):
    embedder, store = temp_qdrant_store
    chunks = [
        DocumentChunk(
            chunk_id="c1",
            doc_name="manual.pdf",
            page_number=5,
            text="Van an toàn sẽ xả áp khi áp suất vượt quá 10 bar."
        ),
        DocumentChunk(
            chunk_id="c2",
            doc_name="manual.pdf",
            page_number=8,
            text="Bôi trơn ổ bi bằng dầu nhờn định kỳ 3 tháng một lần."
        )
    ]
    # Upsert with embeddings
    vectors = embedder.embed_texts([c.text for c in chunks])
    store.upsert_chunks_with_vectors(chunks, vectors)

    # Search
    query_vec = embedder.embed_query("Khi nào van an toàn mở?")
    results = store.search(query_vec, top_k=1)

    assert len(results) == 1
    assert results[0].chunk.page_number == 5
    assert "Van an toàn" in results[0].chunk.text
    assert results[0].score > 0.0


def test_qdrant_cloud_initialization():
    from unittest.mock import MagicMock, patch

    with patch("src.vector_store.qdrant_store.QdrantClient") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        mock_instance.get_collections.return_value.collections = []

        store = QdrantVectorStore(
            url="https://xyz-example.qdrant.io:6333",
            api_key="secret-api-key",
            collection_name="cloud_collection"
        )

        mock_client_cls.assert_called_once_with(
            url="https://xyz-example.qdrant.io:6333",
            api_key="secret-api-key",
            timeout=60.0
        )
        assert store.url == "https://xyz-example.qdrant.io:6333"
        assert store.api_key == "secret-api-key"


