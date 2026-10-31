"""Sparse BM25 retriever with technical symbol tokenization and score normalization."""

import math
import re
from typing import List, Optional
import numpy as np
from rank_bm25 import BM25Okapi

from src.models import DocumentChunk, RetrievalResult
from src.retrieval.base import BaseRetriever

TOKEN_PATTERN = re.compile(r"[\w]+|[^\s\w]+")


class SafeBM25Okapi(BM25Okapi):
    """Subclass of BM25Okapi ensuring strictly positive IDF values.

    Standard BM25Okapi can assign 0 or negative IDF when corpus size is small
    (e.g., N <= 2) or for very frequent terms. This subclass applies Lucene-style
    smoothing (log(1 + (N - n + 0.5) / (n + 0.5))) to guarantee positive IDF floor.
    """

    def _calc_idf(self, nd):
        super()._calc_idf(nd)
        for word, val in self.idf.items():
            if val <= 0:
                freq = nd[word]
                self.idf[word] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))


class BM25Retriever(BaseRetriever):
    """Sparse retriever utilizing BM25Okapi with symbol-aware tokenization."""

    def __init__(self, chunks: Optional[List[DocumentChunk]] = None) -> None:
        self.chunks: List[DocumentChunk] = []
        self.bm25: Optional[SafeBM25Okapi] = None
        if chunks:
            self.index_chunks(chunks)

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text preserving alphanumeric terms and punctuation symbols.

        Preserves technical identifiers such as TCVN 9222:2012, ISO 9906:1999,
        and model codes like TKE-380.
        """
        if not text or not isinstance(text, str):
            return []
        return TOKEN_PATTERN.findall(text.lower())

    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Index a batch of document chunks into the BM25 model.

        Updates existing chunks with matching chunk_ids or appends new chunks,
        then rebuilds the tokenized corpus index.
        """
        if not chunks:
            return 0

        existing_ids = {c.chunk_id: idx for idx, c in enumerate(self.chunks)}
        for chunk in chunks:
            if chunk.chunk_id in existing_ids:
                self.chunks[existing_ids[chunk.chunk_id]] = chunk
            else:
                existing_ids[chunk.chunk_id] = len(self.chunks)
                self.chunks.append(chunk)

        tokenized_corpus = [self.tokenize(c.text) for c in self.chunks]
        self.bm25 = SafeBM25Okapi(tokenized_corpus)
        return len(chunks)

    def delete_by_doc_name(self, doc_name: str) -> int:
        """Delete all chunks belonging to doc_name and rebuild BM25 index."""
        import unicodedata
        nfc_target = unicodedata.normalize("NFC", doc_name)
        initial_len = len(self.chunks)
        self.chunks = [
            c for c in self.chunks
            if unicodedata.normalize("NFC", c.doc_name) != nfc_target
        ]
        deleted_count = initial_len - len(self.chunks)
        if self.chunks:
            tokenized_corpus = [self.tokenize(c.text) for c in self.chunks]
            self.bm25 = SafeBM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None
        return deleted_count

    def clear(self) -> None:
        """Clear all indexed chunks."""
        self.chunks = []
        self.bm25 = None

    def get_indexed_doc_names(self) -> set:
        """Return distinct document names currently indexed."""
        import unicodedata
        return {unicodedata.normalize("NFC", c.doc_name) for c in self.chunks if c.doc_name}

    def search(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        """Search for top_k relevant DocumentChunks matching the query.

        Normalizes raw BM25 scores to [0.0, 1.0] relative to the maximum score,
        and returns results ordered descending by score.
        """
        if not query or not isinstance(query, str) or not query.strip():
            return []
        if top_k <= 0 or not self.chunks or self.bm25 is None:
            return []

        tokens = self.tokenize(query)
        if not tokens:
            return []

        raw_scores = self.bm25.get_scores(tokens)
        max_score = float(np.max(raw_scores)) if len(raw_scores) > 0 else 0.0
        if max_score <= 0.0:
            return []

        scored = []
        for chunk, raw_score in zip(self.chunks, raw_scores):
            if raw_score > 0.0:
                norm_score = min(1.0, max(0.0, float(raw_score / max_score)))
                scored.append((chunk, norm_score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            RetrievalResult(chunk=chunk, score=score)
            for chunk, score in scored[:top_k]
        ]
