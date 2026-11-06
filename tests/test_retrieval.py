# tests/test_retrieval.py
from src.models import DocumentChunk
from src.retrieval.base import BaseRetriever
from src.retrieval.local import LocalRetriever
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore

def test_local_retriever_conforms_to_base(tmp_path):
    embedder = EmbeddingModel("all-MiniLM-L6-v2")
    store = QdrantVectorStore(storage_path=str(tmp_path / "qdrant"), collection_name="test_retrieval")
    retriever = LocalRetriever(embedding_model=embedder, vector_store=store)

    assert isinstance(retriever, BaseRetriever)

    # Ingest 1 chunk
    chunk = DocumentChunk(chunk_id="c1", doc_name="guide.pdf", page_number=2, text="Nhiet do toi da cho phep la 80 do C.")
    retriever.index_chunks([chunk])

    # Search
    results = retriever.search("nhiet do toi da bao nhieu", top_k=1)
    assert len(results) == 1
    assert results[0].chunk.page_number == 2
    assert results[0].chunk.doc_name == "guide.pdf"

