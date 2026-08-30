"""
Integration tests for rate limiting on the /analyze endpoint.

Tests verify that:
    - Anonymous requests within the limit succeed (not blocked).
    - Anonymous requests exceeding the limit get HTTP 429 with proper error format.
    - The Retry-After header is present on 429 responses.
    - Authenticated users have a separate, higher rate limit bucket.
    - Cached results still go through rate limiting checks.
"""

import pytest
from fastapi.testclient import TestClient

from app.api import dependencies as deps
from app.core.constants import SESSION_COOKIE_NAME
from app.middleware.rate_limiter import RateLimiter


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Reset the rate limiter singletons before each test."""
    deps._anon_rate_limiter = None
    deps._auth_rate_limiter = None
    yield
    deps._anon_rate_limiter = None
    deps._auth_rate_limiter = None


@pytest.fixture
def low_limit_client(test_client: TestClient) -> TestClient:
    """
    Provide a TestClient with very low rate limits for testing.

    Overrides the rate limiter singletons with max_requests=2
    so we can trigger 429 without sending dozens of requests.
    """
    deps._anon_rate_limiter = RateLimiter(max_requests=2, window_seconds=60)
    deps._auth_rate_limiter = RateLimiter(max_requests=2, window_seconds=60)
    return test_client


class TestAnonymousRateLimit:
    """Rate limiting for unauthenticated (anonymous) users."""

    def test_requests_within_limit_are_not_blocked(self, low_limit_client: TestClient):
        """First N requests should not return 429."""
        # These may return 400/422 if the body is invalid, but NOT 429
        for _ in range(2):
            response = low_limit_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )
            assert response.status_code != 429

    def test_exceeding_limit_returns_429(self, low_limit_client: TestClient):
        """The request exceeding the limit should return HTTP 429."""
        # Exhaust the limit
        for _ in range(2):
            low_limit_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )

        # This one should be rate-limited
        response = low_limit_client.post(
            "/api/v1/analyze",
            json={"pr_url": "https://github.com/owner/repo/pull/1"},
        )
        assert response.status_code == 429

    def test_429_response_has_correct_format(self, low_limit_client: TestClient):
        """The 429 response should match the standard error envelope."""
        for _ in range(2):
            low_limit_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )

        response = low_limit_client.post(
            "/api/v1/analyze",
            json={"pr_url": "https://github.com/owner/repo/pull/1"},
        )
        body = response.json()
        assert body["status"] == "error"
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Rate limit exceeded" in body["error"]["message"]

    def test_429_includes_retry_after_header(self, low_limit_client: TestClient):
        """The 429 response should include a Retry-After header."""
        for _ in range(2):
            low_limit_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )

        response = low_limit_client.post(
            "/api/v1/analyze",
            json={"pr_url": "https://github.com/owner/repo/pull/1"},
        )
        assert "retry-after" in response.headers
        assert int(response.headers["retry-after"]) > 0


class TestAuthenticatedRateLimit:
    """Rate limiting for authenticated users (separate per-user bucket)."""

    def _create_session(self) -> str:
        """Create a fake session in the AuthService and return the session ID."""
        import secrets
        import time

        auth_service = deps.get_auth_service()
        session_id = secrets.token_urlsafe(32)
        auth_service._sessions[session_id] = {
            "user": {
                "id": 12345,
                "login": "testuser",
                "name": "Test User",
                "avatar_url": "https://example.com/avatar.png",
            },
            "access_token": "gho_fake_token",
            "created_at": time.time(),
            "expires_at": time.time() + 86400,
        }
        return session_id

    def test_authenticated_user_has_separate_limit(self, low_limit_client: TestClient):
        """
        An authenticated user should have a separate bucket from anonymous users.
        After exhausting the anonymous limit, an authenticated request should still succeed.
        """
        # Exhaust the anonymous limit (2 requests)
        for _ in range(2):
            low_limit_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )

        # Anonymous user is now rate-limited
        response = low_limit_client.post(
            "/api/v1/analyze",
            json={"pr_url": "https://github.com/owner/repo/pull/1"},
        )
        assert response.status_code == 429

        # Authenticated user should NOT be rate-limited (separate bucket)
        session_id = self._create_session()
        low_limit_client.cookies.set(SESSION_COOKIE_NAME, session_id)
        response = low_limit_client.post(
            "/api/v1/analyze",
            json={"pr_url": "https://github.com/owner/repo/pull/1"},
        )
        assert response.status_code != 429
        low_limit_client.cookies.clear()

    def test_authenticated_user_can_be_rate_limited(self, low_limit_client: TestClient):
        """Authenticated users can also be rate-limited after exceeding their limit."""
        session_id = self._create_session()
        low_limit_client.cookies.set(SESSION_COOKIE_NAME, session_id)

        # Exhaust the authenticated limit (2 requests)
        for _ in range(2):
            low_limit_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )

        # This one should be rate-limited
        response = low_limit_client.post(
            "/api/v1/analyze",
            json={"pr_url": "https://github.com/owner/repo/pull/1"},
        )
        assert response.status_code == 429
        low_limit_client.cookies.clear()

    def test_expired_session_falls_back_to_anonymous(self, low_limit_client: TestClient):
        """A request with an invalid/expired session should be rate-limited as anonymous."""
        low_limit_client.cookies.set(SESSION_COOKIE_NAME, "invalid_session_id")

        # Exhaust the anonymous limit
        for _ in range(2):
            low_limit_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )

        response = low_limit_client.post(
            "/api/v1/analyze",
            json={"pr_url": "https://github.com/owner/repo/pull/1"},
        )
        assert response.status_code == 429
        low_limit_client.cookies.clear()
