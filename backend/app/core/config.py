from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = Field(default="dev-secret-change-in-prod")
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Database
    database_url: str = "postgresql+asyncpg://dev:dev@localhost:5432/fastenergpt"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # ChromaDB
    chroma_url: str = "http://localhost:8000"
    chroma_collection_name: str = "fastenergpt_cases"

    # Object Storage (S3-compatible)
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "fastenergpt"

    # LLM API Keys
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    google_api_key: str = ""

    # LLM Models
    primary_model: str = "claude-opus-4-7"
    aux_model: str = "claude-haiku-4-5-20251001"
    cross_val_model: str = "gemini-2.5-pro"
    embedding_model: str = "voyage-3-large"
    rerank_model: str = "rerank-2"

    # Pipeline config
    rag_top_k: int = 20
    rag_top_n: int = 3
    max_design_retries: int = 2
    min_confidence_threshold: str = "high"


settings = Settings()
