"""
In-memory TTL cache for analysis results.

This is a pure-Python, async-safe cache that stores analysis responses
keyed by normalized PR URL. Entries expire after a configurable TTL.

Design decisions:
    - Uses asyncio.Lock for async safety (not threading.Lock, since
      FastAPI runs on an event loop, not a thread pool).
    - Expired entries are evicted lazily on access and proactively
      during set() when max_entries is reached.
    - LRU-style eviction: when full, the oldest entry is removed.

Future migration to Redis:
    1. Create app/cache/redis.py implementing the same get/set/delete interface.
    2. Update app/api/dependencies.py to return the Redis implementation.
    3. AnalysisService code is unchanged.
"""

import asyncio
import time
from typing import Any


class TTLCache:
    """
    Async-safe in-memory cache with TTL expiration and max-entry eviction.

    Attributes:
        ttl: Time-to-live in seconds for each cache entry.
        max_entries: Maximum number of entries before LRU eviction.
    """

    def __init__(self, ttl: int = 300, max_entries: int = 100) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        # Stores {key: (value, expiry_timestamp)}
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """
        Retrieve a value by key if it exists and has not expired.

        Returns None for missing or expired entries. Expired entries
        are removed from the store on access (lazy eviction).
        """
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None

            value, expiry = entry
            if time.monotonic() > expiry:
                # Entry has expired — remove it.
                del self._store[key]
                return None

            return value

    async def set(self, key: str, value: Any) -> None:
        """
        Store a value with the configured TTL.

        If the cache is full, the oldest entry (by insertion order)
        is evicted first.
        """
        async with self._lock:
            # Evict expired entries first.
            self._evict_expired()

            # If still at capacity, remove the oldest entry (first key in dict).
            if len(self._store) >= self._max_entries and key not in self._store:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]

            expiry = time.monotonic() + self._ttl
            self._store[key] = (value, expiry)

    async def delete(self, key: str) -> bool:
        """
        Remove a specific entry. Returns True if the key existed.
        """
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> None:
        """Remove all entries."""
        async with self._lock:
            self._store.clear()

    async def size(self) -> int:
        """Return the number of non-expired entries."""
        async with self._lock:
            self._evict_expired()
            return len(self._store)

    def _evict_expired(self) -> None:
        """Remove all expired entries. Must be called under the lock."""
        now = time.monotonic()
        expired_keys = [k for k, (_, expiry) in self._store.items() if now > expiry]
        for key in expired_keys:
            del self._store[key]
