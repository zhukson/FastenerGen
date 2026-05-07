import json
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = Field(default="dev-secret-change-in-prod")
    # NoDecode prevents pydantic-settings from JSON-decoding the env value
    # (shell stripping quotes from `["a","b"]` would otherwise crash).
    # The validator below normalizes both JSON and comma-separated forms.
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, v):
        if v is None or isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                # Try JSON first; fall back to bracket-stripping if quotes
                # were eaten by the shell (`[a,b]` -> ['a','b']).
                try:
                    return json.loads(s)
                except json.JSONDecodeError:
                    s = s.strip("[]")
            return [item.strip().strip('"').strip("'") for item in s.split(",") if item.strip()]
        return v

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
    claude_model_die_design: str = "claude-sonnet-4-6"  # faster/cheaper for schema-following task

    # Pipeline config
    rag_top_k: int = 20
    rag_top_n: int = 3
    max_design_retries: int = 2
    min_confidence_threshold: str = "high"

    # Output file storage (local dev; production uses MinIO)
    output_base_dir: str = "/tmp/fastenergpt/designs"


settings = Settings()
