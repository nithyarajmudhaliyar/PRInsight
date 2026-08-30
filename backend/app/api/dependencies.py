"""
FastAPI Depends() factories — dependency injection wiring.

This is the single source of truth for all dependency factories.
Every injectable (settings, clients, cache, services) is created here.

Why this file exists:
    - Testing: swap get_github_client with a mock in tests.
    - Future DB: add get_db_session here.
    - Auth: get_auth_service provides authenticated session management.
    - Rate limiting: check_rate_limit enforces per-IP / per-user limits.
"""

from fastapi import Cookie, Request

from app.cache.memory import TTLCache
from app.clients.github_client import GitHubClient
from app.clients.github_oauth_client import GitHubOAuthClient
from app.core.config import Settings, get_settings
from app.core.constants import SESSION_COOKIE_NAME
from app.exceptions.rate_limit import RateLimitExceededError
from app.middleware.rate_limiter import RateLimiter
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
_anon_rate_limiter: RateLimiter | None = None
_auth_rate_limiter: RateLimiter | None = None


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


def _get_anon_rate_limiter() -> RateLimiter:
    """Return the singleton rate limiter for anonymous users."""
    global _anon_rate_limiter
    if _anon_rate_limiter is None:
        settings = get_settings()
        _anon_rate_limiter = RateLimiter(
            max_requests=settings.RATE_LIMIT_ANON_MAX,
            window_seconds=settings.RATE_LIMIT_ANON_WINDOW,
        )
    return _anon_rate_limiter


def _get_auth_rate_limiter() -> RateLimiter:
    """Return the singleton rate limiter for authenticated users."""
    global _auth_rate_limiter
    if _auth_rate_limiter is None:
        settings = get_settings()
        _auth_rate_limiter = RateLimiter(
            max_requests=settings.RATE_LIMIT_AUTH_MAX,
            window_seconds=settings.RATE_LIMIT_AUTH_WINDOW,
        )
    return _auth_rate_limiter


def check_rate_limit(request: Request, prinsight_session: str | None = Cookie(default=None)) -> None:
    """
    FastAPI dependency that enforces rate limits on the analysis endpoint.

    Authenticated users (valid session cookie) are rate-limited per user ID.
    Anonymous users are rate-limited per client IP address.

    Raises:
        RateLimitExceededError: If the client has exceeded their rate limit.
    """
    auth_service = get_auth_service()
    settings = get_settings()

    # Try to identify the user from their session
    user_id: str | None = None
    if prinsight_session:
        try:
            user_data = auth_service.get_current_user(prinsight_session)
            user_id = str(user_data.get("id"))
        except Exception:
            # Invalid or expired session — treat as anonymous
            pass

    if user_id:
        limiter = _get_auth_rate_limiter()
        key = f"user:{user_id}"
        window = settings.RATE_LIMIT_AUTH_WINDOW
    else:
        limiter = _get_anon_rate_limiter()
        # Use X-Forwarded-For when behind a reverse proxy, fall back to client IP
        forwarded = request.headers.get("x-forwarded-for")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        key = f"ip:{client_ip}"
        window = settings.RATE_LIMIT_ANON_WINDOW

    if not limiter.is_allowed(key):
        raise RateLimitExceededError(retry_after=window)

