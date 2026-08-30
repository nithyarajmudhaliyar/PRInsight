"""
Tests for the in-memory sliding window rate limiter.
"""

import time
from unittest.mock import patch

from app.middleware.rate_limiter import RateLimiter


class TestRateLimiter:
    """Unit tests for the RateLimiter class."""

    def test_allows_requests_within_limit(self):
        """Requests within the max_requests limit should be allowed."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is True

    def test_blocks_requests_over_limit(self):
        """The request exceeding max_requests should be denied."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is False

    def test_separate_keys_have_separate_limits(self):
        """Different keys should have independent rate limit buckets."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key2") is True
        # key1 is now exhausted, key2 was separate
        assert limiter.is_allowed("key1") is False
        assert limiter.is_allowed("key2") is False

    def test_window_expiry_resets_limit(self):
        """After the window expires, requests should be allowed again."""
        limiter = RateLimiter(max_requests=1, window_seconds=10)

        # Use the first request
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is False

        # Advance time past the window
        with patch("app.middleware.rate_limiter.time.monotonic", return_value=time.monotonic() + 11):
            assert limiter.is_allowed("key1") is True

    def test_remaining_returns_correct_count(self):
        """remaining() should reflect how many requests are left."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.remaining("key1") == 5
        limiter.is_allowed("key1")
        assert limiter.remaining("key1") == 4
        limiter.is_allowed("key1")
        limiter.is_allowed("key1")
        assert limiter.remaining("key1") == 2

    def test_remaining_never_negative(self):
        """remaining() should return 0, not a negative number."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.is_allowed("key1")
        limiter.is_allowed("key1")  # Denied but doesn't add to window
        assert limiter.remaining("key1") == 0

    def test_cleanup_removes_empty_keys(self):
        """cleanup() should remove keys with no active timestamps."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        limiter.is_allowed("key1")
        limiter.is_allowed("key2")

        # Advance time past the window so entries expire
        with patch("app.middleware.rate_limiter.time.monotonic", return_value=time.monotonic() + 2):
            # Trigger eviction via remaining() to clear deques
            limiter.remaining("key1")
            limiter.remaining("key2")
            limiter.cleanup()
            assert "key1" not in limiter._windows
            assert "key2" not in limiter._windows
