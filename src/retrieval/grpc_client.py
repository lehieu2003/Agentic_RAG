"""gRPC Client Adapter implementing BaseRetriever interface."""

from typing import List
import grpc
from src.models import DocumentChunk, RetrievalResult
from src.retrieval.base import BaseRetriever
from src.rpc import retrieval_pb2, retrieval_pb2_grpc


class GrpcRetriever(BaseRetriever):
    """Retriever client communicating with a remote gRPC RetrievalService."""

    def __init__(self, host: str = "localhost", port: int = 50051):
        self.host = host
        self.port = port
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = retrieval_pb2_grpc.RetrievalServiceStub(self.channel)

    def search(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """Send RPC request to retrieve nearest chunks from remote server."""
        if not query.strip():
            return []

        request = retrieval_pb2.SearchRequest(
            query=query,
            top_k=top_k
        )

        try:
            response = self.stub.Search(request, timeout=10.0)
        except grpc.RpcError as e:
            raise ConnectionError(
                f"Failed to communicate with gRPC RetrievalService at {self.host}:{self.port}: {e.details()}"
            ) from e

        results: List[RetrievalResult] = []
        for pb_chunk in response.chunks:
            chunk = DocumentChunk(
                chunk_id=pb_chunk.chunk_id,
                doc_name=pb_chunk.doc_name,
                page_number=pb_chunk.page_number,
                text=pb_chunk.text,
                metadata={}
            )
            results.append(RetrievalResult(chunk=chunk, score=float(pb_chunk.score)))

        return results

    def close(self) -> None:
        """Close gRPC channel connection."""
        if hasattr(self, "channel") and self.channel is not None:
            self.channel.close()

