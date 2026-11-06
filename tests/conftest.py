"""Pytest configuration and global environment fixtures."""

import os

# Ensure HuggingFace Hub doesn't attempt network calls in test runs
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Ensure unit tests use local embedded / in-memory mode rather than hitting external cloud
os.environ["QDRANT_URL"] = ""
os.environ["QDRANT_API_KEY"] = ""
os.environ["QDRANT_PATH"] = ":memory:"

# Keep tests fast and deterministic: use the small cached models instead of the
# production multilingual embedding/reranker pair.
os.environ["EMBEDDING_MODEL"] = "all-MiniLM-L6-v2"
os.environ["RERANKER_MODEL"] = "BAAI/bge-reranker-base"
os.environ["EMBEDDING_MAX_SEQ_LENGTH"] = "256"
os.environ["CHUNK_SIZE_TOKENS"] = "200"

from src.config import settings
settings.qdrant_url = ""
settings.qdrant_api_key = ""
settings.qdrant_path = ":memory:"
settings.embedding_model = "all-MiniLM-L6-v2"
settings.reranker_model = "BAAI/bge-reranker-base"
settings.embedding_max_seq_length = 256
settings.chunk_size_tokens = 200


# Ensure unit tests do not make external LLM network calls
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""



