"""SentenceTransformers embedding wrapper."""

from typing import List
from sentence_transformers import SentenceTransformer


class EmbeddingModel:
    """Wrapper around SentenceTransformer for generating normalized text embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        if hasattr(self._model, "get_embedding_dimension"):
            self._dimension = self._model.get_embedding_dimension() or 384
        else:
            self._dimension = self._model.get_sentence_embedding_dimension() or 384

    @property
    def dimension(self) -> int:
        """Return the vector embedding dimension."""
        return self._dimension

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Compute embeddings for a list of texts.

        Args:
            texts: List of strings to embed.

        Returns:
            List of float vector embeddings.
        """
        if not texts:
            return []
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Compute embedding for a single search query.

        Args:
            query: Query string.

        Returns:
            Float vector embedding.
        """
        embedding = self._model.encode(query, normalize_embeddings=True, show_progress_bar=False)
        return embedding.tolist()
