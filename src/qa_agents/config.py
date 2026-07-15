from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_vision_model: str = "qwen2.5vl:7b"
    ollama_timeout_seconds: int = Field(default=900, ge=10)
    ollama_temperature: float = Field(default=0.1, ge=0, le=2)
    ollama_context_window: int = Field(default=16_384, ge=4_096)
    ollama_max_output_tokens: int = Field(default=12_288, ge=1_024)
    figma_access_token: str | None = None
    qa_agent_max_source_chars: int = Field(default=80_000, ge=5_000)
    qa_agent_max_upload_mb: int = Field(default=25, ge=1, le=250)


@lru_cache
def get_settings() -> Settings:
    return Settings()
