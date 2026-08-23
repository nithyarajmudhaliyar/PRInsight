"""
FastAPI Depends() factories — dependency injection wiring.

This is the single source of truth for all dependency factories.
Every injectable (settings, clients, cache, services) is created here.

Why this file exists:
    - Testing: swap get_github_client with a mock in tests.
    - Future DB: add get_db_session here.
    - Auth: get_auth_service provides authenticated session management.
"""

from app.cache.memory import TTLCache
from app.clients.github_client import GitHubClient
from app.clients.github_oauth_client import GitHubOAuthClient
from app.core.config import Settings, get_settings
from app.services.analysis_service import AnalysisService
from app.services.auth_service import AuthService

# ── Module-level singletons ──────────────────────────────────────────────────
# These are safe as singletons because:
#   - TTLCache uses asyncio.Lock (async-safe, not request-scoped)
#   - GitHubClient wraps a single HTTPX AsyncClient (connection-pooled)
#   - GitHubOAuthClient wraps a single HTTPX AsyncClient (connection-pooled)
#   - AuthService stores sessions in-memory (server-scoped)
# They are created lazily on first access.

_cache: TTLCache | None = None
_github_client: GitHubClient | None = None
_github_oauth_client: GitHubOAuthClient | None = None
_auth_service: AuthService | None = None


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


def get_github_oauth_client() -> GitHubOAuthClient:
    """
    Return the singleton GitHubOAuthClient instance.

    Created on first call using settings from get_settings().
    """
    global _github_oauth_client
    if _github_oauth_client is None:
        settings = get_settings()
        _github_oauth_client = GitHubOAuthClient(settings)
    return _github_oauth_client


def get_auth_service() -> AuthService:
    """
    Return the singleton AuthService instance.

    Uses the singleton GitHubOAuthClient and settings.
    Singleton because AuthService holds in-memory session state.
    """
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService(
            oauth_client=get_github_oauth_client(),
            settings=get_settings(),
        )
    return _auth_service


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

