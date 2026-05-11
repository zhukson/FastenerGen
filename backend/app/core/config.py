import json
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    # LLM API Keys
    anthropic_api_key: str = ""

    # LLM Models
    primary_model: str = "claude-opus-4-7"
    aux_model: str = "claude-haiku-4-5-20251001"
    claude_model_die_design: str = "claude-sonnet-4-6"

    # Pipeline config
    max_design_retries: int = 2
    min_confidence_threshold: str = "high"

    # Local output storage for ProcessForming schema and reasoning sidecars.
    output_base_dir: str = "/tmp/fastenergpt/designs"


settings = Settings()
