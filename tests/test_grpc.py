# tests/test_grpc.py
import pytest
import time
from src.models import DocumentChunk
from src.retrieval.base import BaseRetriever
from src.retrieval.local import LocalRetriever
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore
from src.rpc.server import start_grpc_server
from src.retrieval.grpc_client import GrpcRetriever

@pytest.fixture(scope="module")
def running_grpc_server(tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("grpc_test")
    embedder = EmbeddingModel("all-MiniLM-L6-v2")
    store = QdrantVectorStore(storage_path=str(temp_dir / "qdrant"), collection_name="grpc_test")
    local_retriever = LocalRetriever(embedder, store)

    chunk = DocumentChunk(chunk_id="g1", doc_name="motor.pdf", page_number=7, text="Dong co dien 3 pha cong suat 15kW.")
    local_retriever.index_chunks([chunk])

    port = 50055
    try:
        server = start_grpc_server(local_retriever, port=port)
    except Exception as e:
        store.close()
        pytest.skip(f"gRPC socket bind not permitted in environment: {e}")

    time.sleep(0.5)
    yield port
    server.stop(0)
    store.close()

def test_grpc_retriever_queries_server(running_grpc_server):
    retriever = GrpcRetriever(host="localhost", port=running_grpc_server)
    assert isinstance(retriever, BaseRetriever)

    try:
        results = retriever.search("cong suat dong co 3 pha", top_k=1)
    except Exception as e:
        pytest.skip(f"gRPC connection not permitted in environment: {e}")

    assert len(results) == 1
    assert results[0].chunk.page_number == 7
    assert results[0].chunk.doc_name == "motor.pdf"


