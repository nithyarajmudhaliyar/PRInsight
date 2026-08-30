"""
Integration tests for rate limiting on the /analyze endpoint.

Tests verify that:
    - Requests within the limit succeed (not blocked).
    - Requests exceeding the limit get HTTP 429 with proper error format.
    - The Retry-After header is present on 429 responses.
"""

import pytest
from fastapi.testclient import TestClient

from app.api import dependencies as deps
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
