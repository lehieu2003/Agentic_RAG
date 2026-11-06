"""Text chunker that splits document pages while preserving page numbers and metadata."""

import hashlib
import unicodedata
from typing import Any, Dict, List, Optional
from src.models import DocumentChunk


def _split_text_with_overlap(text: str, chunk_size: int = 1200, chunk_overlap: int = 200) -> List[str]:
    """Split a single string into overlapping chunks respecting natural boundaries (paragraphs, sentences)."""
    text = text.strip()
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    # Priority of natural text separators: paragraphs first, then sentence ends, then lines, then words
    separators = ["\n\n", ".\n", ".\r\n", ". ", "?\n", "? ", "!\n", "! ", ";\n", "\n", " "]

    while start < text_len:
        end = start + chunk_size

        if end >= text_len:
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Look for natural breakpoint near the end
        boundary = -1
        for sep in separators:
            pos = text.rfind(sep, start, end)
            if pos != -1 and pos > start + (chunk_size // 2):
                boundary = pos + len(sep)
                break

        if boundary != -1:
            end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward with overlap, ensuring we do not cut words in half
        next_start = max(start + 1, end - chunk_overlap)
        if next_start < end:
            space_pos = text.find(" ", next_start, end)
            newline_pos = text.find("\n", next_start, end)
            candidates = [p for p in (space_pos, newline_pos) if p != -1]
            if candidates:
                next_start = min(candidates) + 1
        start = next_start

    return chunks


def _tokenize_to_ids(tokenizer: Any, text: str) -> List[int]:
    """Tokenize text without triggering the model's max-length warning."""
    tokenize = getattr(tokenizer, "tokenize", None)
    convert = getattr(tokenizer, "convert_tokens_to_ids", None)
    if callable(tokenize) and callable(convert):
        try:
            tokens = tokenize(text, verbose=False)
        except TypeError:
            tokens = tokenize(text)
        return list(convert(tokens))

    try:
        return list(tokenizer.encode(text, add_special_tokens=False, verbose=False))
    except TypeError:
        return list(tokenizer.encode(text, add_special_tokens=False))


def _decode_token_ids(tokenizer: Any, token_ids: List[int]) -> str:
    """Decode token ids into text using the tokenizer's standard options."""
    return tokenizer.decode(
        token_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    ).strip()


def _split_text_by_tokens(
    text: str,
    tokenizer: Any,
    max_tokens: int,
    overlap_tokens: int = 0,
) -> List[str]:
    """Split text into overlapping token windows using the embedding tokenizer.

    Token-window chunking guarantees each chunk fits the embedding model context
    window (including the special-token margin reserved by the caller). It is used
    in production while the character-based splitter remains the test/fallback path.
    """
    text = text.strip()
    if not text:
        return []

    if not hasattr(tokenizer, "encode") or not hasattr(tokenizer, "decode"):
        return _split_text_with_overlap(text)

    token_ids = _tokenize_to_ids(tokenizer, text)
    if len(token_ids) <= max_tokens:
        return [text]

    max_tokens = max(1, int(max_tokens))
    overlap_tokens = max(0, min(int(overlap_tokens), max_tokens - 1))
    step = max(1, max_tokens - overlap_tokens)

    chunks: List[str] = []
    start = 0
    while start < len(token_ids):
        window = token_ids[start:start + max_tokens]
        if not window:
            break

        chunk = _decode_token_ids(tokenizer, window)
        # Decode/re-encode is not always perfectly invertible (added spaces,
        # word-piece merges). Enforce the hard limit after decoding.
        decoded_ids = _tokenize_to_ids(tokenizer, chunk)
        if len(decoded_ids) > max_tokens:
            chunk = _decode_token_ids(tokenizer, decoded_ids[:max_tokens])

        if chunk and (not chunks or chunk != chunks[-1]):
            chunks.append(chunk)

        if start + max_tokens >= len(token_ids):
            break
        start += step

    return chunks


def _count_tokens(text: str, tokenizer: Any) -> Optional[int]:
    """Count tokens with the provided tokenizer, returning None if unavailable."""
    if tokenizer is None or not hasattr(tokenizer, "encode"):
        return None
    try:
        return len(_tokenize_to_ids(tokenizer, text))
    except Exception:
        return None


def chunk_document(
    pages: List[Dict[str, Any]],
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    tokenizer: Optional[Any] = None,
    max_tokens: Optional[int] = None,
    overlap_tokens: Optional[int] = None,
) -> List[DocumentChunk]:
    """Split multiple pages into DocumentChunk objects, preserving document and page metadata.

    Args:
        pages: List of dicts with keys 'doc_name', 'page_number', 'text'.
        chunk_size: Maximum character length per chunk (character mode).
        chunk_overlap: Number of overlapping characters (character mode).
        tokenizer: Optional HuggingFace tokenizer. When provided together with
            ``max_tokens``, token-aware chunking is used instead of character mode.
        max_tokens: Maximum number of tokens per chunk (token mode).
        overlap_tokens: Number of overlapping tokens (token mode).

    Returns:
        List of DocumentChunk instances.
    """
    use_token_chunking = tokenizer is not None and max_tokens is not None and max_tokens > 0
    document_chunks: List[DocumentChunk] = []

    for page in pages:
        raw_doc_name = page.get("doc_name", "unknown")
        doc_name = unicodedata.normalize("NFC", str(raw_doc_name))
        page_number = int(page.get("page_number", 1))
        page_text = page.get("text", "")
        is_scanned = bool(page.get("is_scanned", False))

        if use_token_chunking:
            text_chunks = _split_text_by_tokens(
                page_text,
                tokenizer=tokenizer,
                max_tokens=int(max_tokens),
                overlap_tokens=int(overlap_tokens or 0),
            )
        else:
            text_chunks = _split_text_with_overlap(
                text=page_text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

        for idx, chunk_text in enumerate(text_chunks):
            # Deterministic, unique hash for the chunk
            hash_input = f"{doc_name}_{page_number}_{idx}_{chunk_text[:30]}".encode("utf-8")
            chunk_id = hashlib.sha256(hash_input).hexdigest()[:16]

            metadata: Dict[str, Any] = {
                "chunk_index": idx,
                "is_scanned": is_scanned,
                "total_page_chunks": len(text_chunks),
                "chunk_method": "token" if use_token_chunking else "char",
            }
            if use_token_chunking:
                metadata["token_count"] = _count_tokens(chunk_text, tokenizer)

            document_chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_name=doc_name,
                    page_number=page_number,
                    text=chunk_text,
                    metadata=metadata,
                )
            )

    return document_chunks
