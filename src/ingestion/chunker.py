"""Text chunker that splits document pages while preserving page numbers and metadata."""

import hashlib
import unicodedata
from typing import Any, Dict, List
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


def chunk_document(
    pages: List[Dict[str, Any]],
    chunk_size: int = 1200,
    chunk_overlap: int = 200
) -> List[DocumentChunk]:
    """Split multiple pages into DocumentChunk objects, preserving document and page metadata.

    Args:
        pages: List of dicts with keys 'doc_name', 'page_number', 'text'.
        chunk_size: Maximum character length per chunk.
        chunk_overlap: Number of overlapping characters between consecutive chunks.

    Returns:
        List of DocumentChunk instances.
    """
    document_chunks: List[DocumentChunk] = []

    for page in pages:
        raw_doc_name = page.get("doc_name", "unknown")
        doc_name = unicodedata.normalize("NFC", str(raw_doc_name))
        page_number = int(page.get("page_number", 1))
        page_text = page.get("text", "")
        is_scanned = bool(page.get("is_scanned", False))

        text_chunks = _split_text_with_overlap(
            text=page_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        for idx, chunk_text in enumerate(text_chunks):
            # Deterministic, unique hash for the chunk
            hash_input = f"{doc_name}_{page_number}_{idx}_{chunk_text[:30]}".encode("utf-8")
            chunk_id = hashlib.sha256(hash_input).hexdigest()[:16]

            document_chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_name=doc_name,
                    page_number=page_number,
                    text=chunk_text,
                    metadata={
                        "chunk_index": idx,
                        "is_scanned": is_scanned,
                        "total_page_chunks": len(text_chunks)
                    }
                )
            )

    return document_chunks

