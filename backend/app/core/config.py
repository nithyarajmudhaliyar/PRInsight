"""
Application configuration via Pydantic Settings.

All environment variables are managed through the Settings class.
Runtime values override the defaults defined in constants.py.

Usage:
    from app.core.config import get_settings
    settings = get_settings()
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_CACHE_MAX_ENTRIES,
    DEFAULT_CACHE_TTL_SECONDS,
    GITHUB_API_BASE_URL,
    GITHUB_DEFAULT_TIMEOUT,
    GITHUB_MAX_RETRIES,
    MAX_CONCURRENT_REQUESTS,
    MAX_PRS_TO_ANALYZE,
)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.

    GITHUB_TOKEN has no default — Pydantic will raise a ValidationError
    at startup if it is missing, causing a fast and clear failure.
    """

    # ── Application ────────────────────────────────────────────────────────
    APP_NAME: str = APP_NAME
    APP_VERSION: str = APP_VERSION
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Server ─────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── GitHub (REQUIRED) ──────────────────────────────────────────────────
    GITHUB_TOKEN: str  # No default → required
    GITHUB_API_BASE_URL: str = GITHUB_API_BASE_URL
    GITHUB_API_TIMEOUT: int = GITHUB_DEFAULT_TIMEOUT
    GITHUB_MAX_RETRIES: int = GITHUB_MAX_RETRIES

    # ── CORS ───────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # ── Cache ──────────────────────────────────────────────────────────────
    CACHE_TTL_SECONDS: int = DEFAULT_CACHE_TTL_SECONDS
    CACHE_MAX_ENTRIES: int = DEFAULT_CACHE_MAX_ENTRIES

    # ── Concurrency ────────────────────────────────────────────────────────
    MAX_CONCURRENT_REQUESTS: int = MAX_CONCURRENT_REQUESTS

    # ── Pagination ─────────────────────────────────────────────────────────
    MAX_PRS_TO_ANALYZE: int = MAX_PRS_TO_ANALYZE

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.

    Using @lru_cache ensures the .env file is read only once.
    The Settings object is then injected into FastAPI routes via Depends().
    """
    return Settings()
