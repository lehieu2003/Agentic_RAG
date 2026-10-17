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
