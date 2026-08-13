"""
Unit tests for app.cache.memory.TTLCache.

Tests cover:
    - Basic get/set operations
    - TTL expiration
    - Max entries eviction
    - Delete and clear operations
    - Async safety
"""

import asyncio
import time
from unittest.mock import patch

import pytest

from app.cache.memory import TTLCache


@pytest.fixture
def cache():
    """Fresh cache with short TTL for testing."""
    return TTLCache(ttl=2, max_entries=3)


class TestTTLCache:
    """Tests for TTLCache."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing_key_returns_none(self, cache):
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_expired_key_returns_none(self, cache):
        """Simulate TTL expiration by patching time.monotonic."""
        await cache.set("key1", "value1")

        # Advance time past TTL
        with patch("app.cache.memory.time.monotonic", return_value=time.monotonic() + 10):
            result = await cache.get("key1")
            assert result is None

    @pytest.mark.asyncio
    async def test_expired_key_is_removed_from_store(self, cache):
        await cache.set("key1", "value1")

        with patch("app.cache.memory.time.monotonic", return_value=time.monotonic() + 10):
            await cache.get("key1")  # Triggers lazy eviction
            size = await cache.size()
            assert size == 0

    @pytest.mark.asyncio
    async def test_max_entries_eviction(self, cache):
        """Cache with max_entries=3 should evict oldest when a 4th entry is added."""
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)
        await cache.set("d", 4)  # Should evict "a"

        assert await cache.get("a") is None
        assert await cache.get("b") == 2
        assert await cache.get("c") == 3
        assert await cache.get("d") == 4

    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self, cache):
        await cache.set("key1", "old")
        await cache.set("key1", "new")
        result = await cache.get("key1")
        assert result == "new"

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, cache):
        await cache.set("key1", "value1")
        deleted = await cache.delete("key1")
        assert deleted is True
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_missing_key(self, cache):
        deleted = await cache.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.clear()
        assert await cache.size() == 0

    @pytest.mark.asyncio
    async def test_size_excludes_expired(self, cache):
        await cache.set("a", 1)
        await cache.set("b", 2)

        with patch("app.cache.memory.time.monotonic", return_value=time.monotonic() + 10):
            size = await cache.size()
            assert size == 0

    @pytest.mark.asyncio
    async def test_stores_complex_objects(self, cache):
        data = {"nested": {"key": [1, 2, 3]}}
        await cache.set("complex", data)
        result = await cache.get("complex")
        assert result == data
