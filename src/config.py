"""Configuration management using Pydantic Settings."""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    app_name: str = "Document Q&A Assistant"
    upload_dir: str = "data/uploads"
    qdrant_path: str = "data/qdrant_storage"
    qdrant_collection: str = "technical_documents"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    embedding_model: str = "all-MiniLM-L6-v2"
    llm_provider: Literal["gemini", "openai", "mock"] = "gemini"
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    grpc_port: int = 50051
    grpc_host: str = "localhost"
    retrieval_mode: Literal["local", "grpc"] = "local"
    min_relevance_score: float = 0.35
    reranker_model: str = "BAAI/bge-reranker-base"
    hybrid_rrf_k: int = 60
    hybrid_candidate_top_k: int = 20
    rerank_top_k: int = 5
    chunk_size: int = 1200
    chunk_overlap: int = 200
    max_retries: int = 1
    max_gen_retries: int = 1
    candidate_pool_size: int = 25
    top_preservation_k: int = 2
    complex_query_threshold: int = 250
    complex_query_top_k: int = 12
    max_citation_page_range: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

