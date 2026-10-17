"""Retrieval module containing BaseRetriever interface and implementations."""

from src.retrieval.base import BaseRetriever
from src.retrieval.local import LocalRetriever
from src.retrieval.grpc_client import GrpcRetriever

__all__ = ["BaseRetriever", "LocalRetriever", "GrpcRetriever"]
