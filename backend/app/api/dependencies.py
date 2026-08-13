"""
FastAPI Depends() factories — dependency injection wiring.

This is the single source of truth for all dependency factories.
Every injectable (settings, clients, cache, services) is created here.

Why this file exists:
    - Testing: swap get_github_client with a mock in tests.
    - Future DB: add get_db_session here.
    - Future Auth: add get_current_user here.
"""

from app.cache.memory import TTLCache
from app.clients.github_client import GitHubClient
from app.core.config import Settings, get_settings
from app.services.analysis_service import AnalysisService

# ── Module-level singletons ──────────────────────────────────────────────────
# These are safe as singletons because:
#   - TTLCache uses asyncio.Lock (async-safe, not request-scoped)
#   - GitHubClient wraps a single HTTPX AsyncClient (connection-pooled)
# They are created lazily on first access.

_cache: TTLCache | None = None
_github_client: GitHubClient | None = None


def get_cache() -> TTLCache:
    """
    Return the singleton TTLCache instance.

    Created on first call using settings from get_settings().
    """
    global _cache
    if _cache is None:
        settings = get_settings()
        _cache = TTLCache(
            ttl=settings.CACHE_TTL_SECONDS,
            max_entries=settings.CACHE_MAX_ENTRIES,
        )
    return _cache


def get_github_client() -> GitHubClient:
    """
    Return the singleton GitHubClient instance.

    Created on first call using settings from get_settings().
    """
    global _github_client
    if _github_client is None:
        settings = get_settings()
        _github_client = GitHubClient(settings)
    return _github_client


def get_analysis_service() -> AnalysisService:
    """
    Build an AnalysisService with all dependencies injected.

    This is a zero-argument factory because FastAPI's Depends() system
    inspects the function signature. If parameters have type annotations
    like `GitHubClient`, FastAPI tries to resolve them as sub-dependencies
    (Pydantic models or query params), causing a startup crash.

    For test overrides, use FastAPI's app.dependency_overrides mechanism:
        app.dependency_overrides[get_analysis_service] = lambda: mock_service
    """
    return AnalysisService(
        github_client=get_github_client(),
        cache=get_cache(),
        settings=get_settings(),
    )
