"""Cross-Encoder reranker module with lazy model initialization."""

from typing import Any, List, Optional
import numpy as np

from src.models import RetrievalResult

# Module-level placeholder so monkeypatching or patch can target this symbol
CrossEncoder: Any = None


class CrossEncoderReranker:
    """Reranks retrieved candidate chunks using a local CrossEncoder model."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        device: Optional[str] = None,
    ) -> None:
        """Initialize CrossEncoderReranker with model specifications.

        Args:
            model_name: HuggingFace model identifier for the cross-encoder.
            device: Computing device ('cpu', 'cuda', 'mps', or None for auto).
        """
        self.model_name = model_name
        self.device = device
        self._model = None

    def _get_model(self):
        """Lazily initialize and return the CrossEncoder instance."""
        if self._model is None:
            ce_cls = globals().get("CrossEncoder")
            if ce_cls is None:
                from sentence_transformers import CrossEncoder as ce_cls
            self._model = ce_cls(self.model_name, device=self.device)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: List[RetrievalResult],
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """Rerank candidates based on cross-encoder similarity with query.

        Args:
            query: User's question or search query string.
            candidates: List of candidate RetrievalResult instances.
            top_k: Maximum number of reranked candidates to return.

        Returns:
            List of RetrievalResult instances sorted descending by cross-encoder score.
        """
        if not candidates or top_k <= 0:
            return []

        if not query or not isinstance(query, str) or not query.strip():
            return []

        model = self._get_model()
        pairs = [(query, candidate.chunk.text) for candidate in candidates]
        raw_scores = model.predict(pairs)

        if isinstance(raw_scores, (int, float, np.floating)):
            scores = [float(raw_scores)]
        elif hasattr(raw_scores, "__iter__"):
            scores = [float(s) for s in raw_scores]
        else:
            scores = [float(raw_scores)]

        reranked = [
            RetrievalResult(chunk=candidate.chunk, score=score)
            for candidate, score in zip(candidates, scores)
        ]

        reranked.sort(key=lambda r: r.score, reverse=True)
        return reranked[:top_k]
