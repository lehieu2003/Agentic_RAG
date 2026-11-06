"""gRPC Server implementation hosting the RetrievalService."""

from concurrent import futures
import grpc
from src.retrieval.base import BaseRetriever
from src.rpc import retrieval_pb2, retrieval_pb2_grpc


class RetrievalServicer(retrieval_pb2_grpc.RetrievalServiceServicer):
    """Servicer delegating search RPC calls to an underlying BaseRetriever."""

    def __init__(self, retriever: BaseRetriever):
        self.retriever = retriever

    def Search(self, request: retrieval_pb2.SearchRequest, context: grpc.ServicerContext) -> retrieval_pb2.SearchResponse:
        """Handle Search RPC method."""
        top_k = request.top_k if request.top_k > 0 else 5
        results = self.retriever.search(query=request.query, top_k=top_k)

        pb_chunks = []
        for r in results:
            pb_chunks.append(
                retrieval_pb2.Chunk(
                    chunk_id=r.chunk.chunk_id,
                    doc_name=r.chunk.doc_name,
                    page_number=r.chunk.page_number,
                    text=r.chunk.text,
                    score=r.score
                )
            )

        return retrieval_pb2.SearchResponse(chunks=pb_chunks)


def start_grpc_server(retriever: BaseRetriever, port: int = 50051) -> grpc.Server:
    """Start and return a running gRPC server hosting RetrievalService.

    Args:
        retriever: Concrete retriever instance to serve.
        port: Port number to bind.

    Returns:
        Running grpc.Server instance.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = RetrievalServicer(retriever)
    retrieval_pb2_grpc.add_RetrievalServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    return server


if __name__ == "__main__":
    import logging
    from src.config import settings
    from src.retrieval.local import LocalRetriever
    from src.vector_store.embedding import EmbeddingModel
    from src.vector_store.qdrant_store import QdrantVectorStore

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("rpc_server")

    embed_model = EmbeddingModel(
        settings.embedding_model,
        device=settings.embedding_device or None,
        max_seq_length=settings.embedding_max_seq_length,
        batch_size=settings.embedding_batch_size,
    )
    store = QdrantVectorStore(
        storage_path=settings.qdrant_path,
        collection_name=settings.qdrant_collection,
        vector_size=embed_model.dimension,
        url=settings.qdrant_url if settings.qdrant_url else None,
        api_key=settings.qdrant_api_key if settings.qdrant_api_key else None
    )
    retriever = LocalRetriever(embedding_model=embed_model, vector_store=store)

    server = start_grpc_server(retriever=retriever, port=settings.grpc_port)
    logger.info("Retrieval gRPC service listening on port %d", settings.grpc_port)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping gRPC service...")
        server.stop(0)
        store.close()


