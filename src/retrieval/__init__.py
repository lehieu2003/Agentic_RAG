"""Retrieval module containing BaseRetriever interface and implementations."""

from src.retrieval.base import BaseRetriever
from src.retrieval.local import LocalRetriever
from src.retrieval.grpc_client import GrpcRetriever
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.hybrid import HybridRetriever

__all__ = [
    "BaseRetriever",
    "LocalRetriever",
    "GrpcRetriever",
    "BM25Retriever",
    "HybridRetriever",
]
