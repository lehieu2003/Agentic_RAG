"""Pytest configuration and global environment fixtures."""

import os

# Ensure HuggingFace Hub doesn't attempt network calls in test runs
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Never touch the real chat history: the FastAPI lifespan creates the session store
# from settings, so every TestClient(app) would otherwise open data/chat_history.db.
import tempfile
_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="rag_test_sessions_"), "chat_history.db")
os.environ["SESSION_DB_PATH"] = _TEST_DB

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
settings.session_db_path = _TEST_DB
settings.embedding_model = "all-MiniLM-L6-v2"
settings.reranker_model = "BAAI/bge-reranker-base"
settings.embedding_max_seq_length = 256
settings.chunk_size_tokens = 200


# Ensure unit tests do not make external LLM network calls
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""



