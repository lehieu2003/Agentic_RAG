"""Helpers for model-aware token budgeting during ingestion."""

from typing import Optional


def get_chunk_token_limit(
    max_seq_length: Optional[int],
    configured_tokens: int,
    margin: int = 64,
) -> int:
    """Return a safe chunk token limit for the embedding model.

    The margin reserves room for the query instruction/prefix and special tokens so
    that both document chunks and search queries fit the embedding context window.
    """
    configured = max(1, int(configured_tokens))
    if max_seq_length is None or max_seq_length <= 0:
        return configured

    # Keep at least a small usable chunk even for very small context models.
    return max(32, min(configured, int(max_seq_length) - max(0, int(margin))))
