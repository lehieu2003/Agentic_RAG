"""Tests for embedding model configuration without loading model weights."""

from src.vector_store.embedding import (
    E5_DOCUMENT_PREFIX,
    E5_INSTRUCT_QUERY_PREFIX,
    E5_QUERY_PREFIX,
    EmbeddingModel,
)


def test_resolve_prefixes_for_e5_instruct():
    query_prefix, document_prefix = EmbeddingModel.resolve_prefixes(
        "intfloat/multilingual-e5-large-instruct"
    )
    assert query_prefix == E5_INSTRUCT_QUERY_PREFIX
    assert document_prefix == ""


def test_resolve_prefixes_for_e5_base_family():
    query_prefix, document_prefix = EmbeddingModel.resolve_prefixes(
        "intfloat/multilingual-e5-small"
    )
    assert query_prefix == E5_QUERY_PREFIX
    assert document_prefix == E5_DOCUMENT_PREFIX


def test_resolve_prefixes_for_non_e5_model():
    assert EmbeddingModel.resolve_prefixes("all-MiniLM-L6-v2") == ("", "")
    assert EmbeddingModel.resolve_prefixes("BAAI/bge-m3") == ("", "")


def test_explicit_prefix_override_wins():
    query_prefix, document_prefix = EmbeddingModel.resolve_prefixes(
        "intfloat/multilingual-e5-large-instruct",
        query_prefix="Q: ",
        document_prefix="D: ",
    )
    assert query_prefix == "Q: "
    assert document_prefix == "D: "
