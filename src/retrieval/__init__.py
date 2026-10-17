"""Retrieval module containing BaseRetriever interface and implementations."""

from src.retrieval.base import BaseRetriever
from src.retrieval.local import LocalRetriever

__all__ = ["BaseRetriever", "LocalRetriever"]

