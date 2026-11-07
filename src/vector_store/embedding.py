"""SentenceTransformers embedding wrapper with model-aware query/document prefixes."""

import logging
from typing import List, Optional

import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

E5_INSTRUCT_QUERY_PREFIX = (
    "Instruct: Given a technical document question, retrieve passages that answer the question\n"
    "Query: "
)
E5_QUERY_PREFIX = "query: "
E5_DOCUMENT_PREFIX = "passage: "


class EmbeddingModel:
    """Wrapper around SentenceTransformer for normalized text embeddings.

    Models in the E5 family require asymmetric query/document encoding, so the
    wrapper resolves the correct prefix from the model name. Other models (for
    example all-MiniLM or bge-m3) are encoded without prefixes.
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-large-instruct",
        device: Optional[str] = None,
        max_seq_length: Optional[int] = None,
        batch_size: int = 32,
        query_prefix: Optional[str] = None,
        document_prefix: Optional[str] = None,
    ):
        self.model_name = model_name
        self.batch_size = max(1, int(batch_size))

        model_kwargs = {}
        if device:
            model_kwargs["device"] = device
        self._model = SentenceTransformer(model_name, **model_kwargs)
        self._ensure_cpu_precision()

        if max_seq_length:
            native_max = getattr(self._model, "max_seq_length", None)
            requested = int(max_seq_length)
            # Never raise the model above its native positional limit; only cap it.
            self._model.max_seq_length = min(requested, int(native_max)) if native_max else requested

        self.query_prefix, self.document_prefix = self.resolve_prefixes(
            model_name,
            query_prefix=query_prefix,
            document_prefix=document_prefix,
        )

        if hasattr(self._model, "get_embedding_dimension"):
            self._dimension = self._model.get_embedding_dimension() or 384
        else:
            self._dimension = self._model.get_sentence_embedding_dimension() or 384

    def _ensure_cpu_precision(self) -> None:
        """Promote float16 checkpoints to float32 when running on CPU.

        Some checkpoints (e.g. multilingual-e5-large-instruct) ship float16
        weights. PyTorch CPU has no fast fp16 path, so inference would be much
        slower than float32; on MPS/CUDA the original dtype is fine and stays.
        """
        try:
            if "cpu" not in str(self._model.device).lower():
                return
            if next(self._model.parameters()).dtype is not torch.float16:
                return
            logger.warning(
                "Embedding model '%s' ships float16 weights; converting to float32 for CPU inference.",
                self.model_name,
            )
            self._model.float()
        except Exception as e:
            logger.warning("Could not inspect embedding model precision: %s", e)

    @staticmethod
    def resolve_prefixes(
        model_name: str,
        query_prefix: Optional[str] = None,
        document_prefix: Optional[str] = None,
    ) -> tuple:
        """Return (query_prefix, document_prefix) for the given embedding model."""
        if query_prefix is not None or document_prefix is not None:
            return query_prefix or "", document_prefix or ""

        name = (model_name or "").lower()
        if "e5" in name and "instruct" in name:
            return E5_INSTRUCT_QUERY_PREFIX, ""
        if "e5" in name:
            return E5_QUERY_PREFIX, E5_DOCUMENT_PREFIX
        return "", ""

    @property
    def dimension(self) -> int:
        """Return the vector embedding dimension."""
        return self._dimension

    @property
    def max_seq_length(self) -> int:
        """Return the maximum number of tokens the embedding model accepts."""
        value = getattr(self._model, "max_seq_length", None)
        return int(value) if value else 512

    @property
    def tokenizer(self):
        """Return the underlying HuggingFace tokenizer, if available."""
        return getattr(self._model, "tokenizer", None)

    def count_tokens(self, text: str) -> Optional[int]:
        """Count tokens with the model tokenizer (returns None when unavailable)."""
        tokenizer = self.tokenizer
        if tokenizer is None:
            return None
        if not text:
            return 0

        tokenize = getattr(tokenizer, "tokenize", None)
        convert = getattr(tokenizer, "convert_tokens_to_ids", None)
        if callable(tokenize) and callable(convert):
            try:
                return len(convert(tokenize(text, verbose=False)))
            except TypeError:
                return len(convert(tokenize(text)))

        try:
            return len(tokenizer.encode(text, add_special_tokens=False, verbose=False))
        except TypeError:
            return len(tokenizer.encode(text, add_special_tokens=False))

    def _encode(self, texts: List[str], prefix: str) -> List[List[float]]:
        if not texts:
            return []
        inputs = [f"{prefix}{text}" for text in texts] if prefix else texts
        embeddings = self._model.encode(
            inputs,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=self.batch_size,
        )
        return embeddings.tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Compute embeddings for a batch of document passages."""
        return self._encode(texts, self.document_prefix)

    def embed_query(self, query: str) -> List[float]:
        """Compute the embedding for a single search query."""
        return self._encode([query], self.query_prefix)[0]
