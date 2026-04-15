"""Application configuration loaded from environment via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./gtg.db"
    """SQLAlchemy URL. SQLite for local dev, Postgres-ready for production."""

    invite_code_bytes: int = 12
    """Entropy bytes used when generating league invite codes."""


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
