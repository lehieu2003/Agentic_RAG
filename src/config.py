"""Configuration management using Pydantic Settings."""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    app_name: str = "Document Q&A Assistant"
    qdrant_path: str = "data/qdrant_storage"
    qdrant_collection: str = "technical_documents"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    embedding_model: str = "all-MiniLM-L6-v2"
    llm_provider: Literal["gemini", "openai", "mock"] = "gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    grpc_port: int = 50051
    grpc_host: str = "localhost"
    retrieval_mode: Literal["local", "grpc"] = "local"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

