"""
In-memory sliding window rate limiter.

Uses a per-key sliding window counter backed by a deque of timestamps.
Appropriate for a single-process deployment; not shared across workers.

Future migration path:
    Replace _windows dict with Redis ZSET + ZRANGEBYSCORE for
    multi-process / multi-node deployments.
"""

import time
from collections import defaultdict, deque


class RateLimiter:
    """
    Sliding window rate limiter.

    Tracks request timestamps per key (IP or user ID) and rejects
    requests once the window limit is exceeded.

    Attributes:
        max_requests: Maximum number of requests allowed in the window.
        window_seconds: Duration of the sliding window in seconds.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        """
        Check if a request from the given key is allowed.

        Removes expired timestamps from the window, then checks
        whether the count is below the limit. If allowed, records
        the current timestamp.

        Args:
            key: Identifier for the rate limit bucket (e.g., IP or user ID).

        Returns:
            True if the request is allowed, False if rate-limited.
        """
        now = time.monotonic()
        window = self._windows[key]
        cutoff = now - self.window_seconds

        # Evict expired entries from the left side of the deque
        while window and window[0] <= cutoff:
            window.popleft()

        if len(window) >= self.max_requests:
            return False

        window.append(now)
        return True

    def remaining(self, key: str) -> int:
        """
        Return the number of requests remaining in the current window.

        Args:
            key: Identifier for the rate limit bucket.

        Returns:
            Non-negative count of remaining requests.
        """
        now = time.monotonic()
        window = self._windows[key]
        cutoff = now - self.window_seconds

        while window and window[0] <= cutoff:
            window.popleft()

        return max(0, self.max_requests - len(window))

    def cleanup(self) -> None:
        """
        Remove keys with no active timestamps.

        Call periodically to prevent unbounded memory growth from
        long-gone IP addresses / users.
        """
        empty_keys = [k for k, v in self._windows.items() if not v]
        for k in empty_keys:
            del self._windows[k]
