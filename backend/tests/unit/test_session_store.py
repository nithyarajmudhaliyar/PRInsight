"""
Unit tests for SessionStore.

Tests cover:
    - Configuration validation (missing/invalid config, fail closed)
    - Fernet encryption and decryption
    - Hashed Redis keys (preventing raw token/session leakage)
    - Redis TTL passing
    - Corrupted ciphertext and decryption failures
    - Redis read/write/delete operation failures
    - Session expiry (both Redis TTL eviction and timestamp expiry)
"""

import hashlib
import json
import time
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet

from app.services.session_store import (
    SessionStore,
    SessionStoreConfigurationError,
    SessionStoreError,
)


@pytest.fixture
def valid_fernet_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def mock_redis():
    """In-memory simulated Redis client for testing."""
    redis = AsyncMock()
    storage = {}

    async def mock_set(key, val, ex=None):
        storage[key] = (val, ex)
        return True

    async def mock_get(key):
        if key in storage:
            return storage[key][0]
        return None

    async def mock_delete(key):
        if key in storage:
            del storage[key]
            return 1
        return 0

    redis.set.side_effect = mock_set
    redis.get.side_effect = mock_get
    redis.delete.side_effect = mock_delete
    redis._storage = storage
    return redis


@pytest.fixture
def configured_store(valid_fernet_key, mock_redis) -> SessionStore:
    """SessionStore with valid Fernet key and mock Redis client."""
    store = SessionStore(
        redis_url="https://example-redis.upstash.io",
        redis_token="valid_token",
        encryption_key=valid_fernet_key,
    )
    store.redis = mock_redis
    return store


class TestSessionStoreConfiguration:
    """Tests for SessionStore configuration validation and fail-closed behavior."""

    def test_configured_when_all_params_valid(self, valid_fernet_key):
        store = SessionStore(
            redis_url="https://example-redis.upstash.io",
            redis_token="test_token",
            encryption_key=valid_fernet_key,
        )
        assert store.is_configured() is True
        assert store._config_error is None

    def test_unconfigured_when_redis_url_missing(self, valid_fernet_key):
        store = SessionStore(
            redis_url="",
            redis_token="test_token",
            encryption_key=valid_fernet_key,
        )
        assert store.is_configured() is False
        assert "Redis URL or token is missing" in store._config_error

    def test_unconfigured_when_redis_token_missing(self, valid_fernet_key):
        store = SessionStore(
            redis_url="https://example-redis.upstash.io",
            redis_token="",
            encryption_key=valid_fernet_key,
        )
        assert store.is_configured() is False
        assert "Redis URL or token is missing" in store._config_error

    def test_unconfigured_when_encryption_key_missing(self):
        store = SessionStore(
            redis_url="https://example-redis.upstash.io",
            redis_token="test_token",
            encryption_key="",
        )
        assert store.is_configured() is False
        assert "OAUTH_TOKEN_ENCRYPTION_KEY is missing" in store._config_error

    def test_unconfigured_when_encryption_key_invalid(self):
        store = SessionStore(
            redis_url="https://example-redis.upstash.io",
            redis_token="test_token",
            encryption_key="invalid-not-base64-key",
        )
        assert store.is_configured() is False
        assert "Invalid OAUTH_TOKEN_ENCRYPTION_KEY" in store._config_error

    async def test_save_session_raises_when_redis_missing(self, valid_fernet_key):
        store = SessionStore(
            redis_url="",
            redis_token="test_token",
            encryption_key=valid_fernet_key,
        )
        with pytest.raises(SessionStoreConfigurationError, match="Redis URL or token is missing"):
            await store.save_session("session_123", {"user": "test"}, 3600)

    async def test_save_session_raises_when_encryption_key_missing(self):
        store = SessionStore(
            redis_url="https://example-redis.upstash.io",
            redis_token="test_token",
            encryption_key="",
        )
        with pytest.raises(SessionStoreConfigurationError, match="OAUTH_TOKEN_ENCRYPTION_KEY is missing"):
            await store.save_session("session_123", {"user": "test"}, 3600)

    async def test_save_session_raises_when_encryption_key_invalid(self):
        store = SessionStore(
            redis_url="https://example-redis.upstash.io",
            redis_token="test_token",
            encryption_key="not-a-fernet-key",
        )
        with pytest.raises(SessionStoreConfigurationError, match="Invalid OAUTH_TOKEN_ENCRYPTION_KEY"):
            await store.save_session("session_123", {"user": "test"}, 3600)

    async def test_get_session_raises_when_unconfigured(self):
        store = SessionStore(
            redis_url="",
            redis_token="",
            encryption_key="",
        )
        with pytest.raises(SessionStoreConfigurationError):
            await store.get_session("session_123")

    async def test_delete_session_raises_when_unconfigured(self):
        store = SessionStore(
            redis_url="",
            redis_token="",
            encryption_key="",
        )
        with pytest.raises(SessionStoreConfigurationError):
            await store.delete_session("session_123")

    async def test_save_oauth_state_raises_when_unconfigured(self):
        store = SessionStore(
            redis_url="",
            redis_token="",
            encryption_key="",
        )
        with pytest.raises(SessionStoreConfigurationError):
            await store.save_oauth_state("state_123", 600)

    async def test_consume_oauth_state_raises_when_unconfigured(self):
        store = SessionStore(
            redis_url="",
            redis_token="",
            encryption_key="",
        )
        with pytest.raises(SessionStoreConfigurationError):
            await store.consume_oauth_state("state_123")


class TestFernetEncryptionDecryption:
    """Tests verifying Fernet encryption and decryption behavior."""

    async def test_session_payload_is_encrypted_in_redis(self, configured_store, mock_redis):
        session_id = "session_xyz_789"
        raw_data = {"user": {"login": "octocat"}, "access_token": "gho_secret_access_token"}
        await configured_store.save_session(session_id, raw_data, ttl_seconds=3600)

        hashed_key = configured_store._hash_session_id(session_id)
        assert hashed_key in mock_redis._storage
        stored_ciphertext, _ = mock_redis._storage[hashed_key]

        # Plaintext secrets must NOT be in the raw stored ciphertext
        assert "gho_secret_access_token" not in stored_ciphertext
        assert "octocat" not in stored_ciphertext

        # Ciphertext must decrypt to the original data using Fernet
        decrypted_bytes = configured_store.fernet.decrypt(stored_ciphertext.encode())
        decrypted_data = json.loads(decrypted_bytes.decode())
        assert decrypted_data["user"]["login"] == "octocat"
        assert decrypted_data["access_token"] == "gho_secret_access_token"

    async def test_get_session_decrypts_and_returns_data(self, configured_store):
        session_id = "session_abc_123"
        raw_data = {"user": {"id": 42, "login": "testdev"}, "access_token": "gho_token_123"}
        await configured_store.save_session(session_id, raw_data, ttl_seconds=1800)

        retrieved = await configured_store.get_session(session_id)
        assert retrieved is not None
        assert retrieved["user"]["id"] == 42
        assert retrieved["user"]["login"] == "testdev"
        assert retrieved["access_token"] == "gho_token_123"


class TestHashedRedisKeys:
    """Tests verifying Redis lookup keys are securely hashed with SHA-256."""

    async def test_session_key_is_sha256_hashed(self, configured_store, mock_redis):
        session_id = "my_sensitive_session_id"
        expected_hash = hashlib.sha256(session_id.encode()).hexdigest()
        expected_key = f"session:{expected_hash}"

        await configured_store.save_session(session_id, {"data": 1}, ttl_seconds=3600)

        # Key in Redis must match the expected hashed key
        assert expected_key in mock_redis._storage
        # Raw session_id must not be part of the key
        assert session_id not in expected_key

    async def test_oauth_state_key_is_sha256_hashed(self, configured_store, mock_redis):
        state = "random_state_nonce"
        expected_hash = hashlib.sha256(state.encode()).hexdigest()
        expected_key = f"oauth_state:{expected_hash}"

        await configured_store.save_oauth_state(state, ttl_seconds=600)

        assert expected_key in mock_redis._storage
        assert state not in expected_key


class TestRedisTTL:
    """Tests verifying Redis TTL expiration parameter is passed."""

    async def test_save_session_passes_ttl(self, configured_store, mock_redis):
        session_id = "ttl_session"
        await configured_store.save_session(session_id, {"data": 1}, ttl_seconds=7200)

        mock_redis.set.assert_awaited()
        call_kwargs = mock_redis.set.call_args.kwargs
        assert call_kwargs.get("ex") == 7200

    async def test_save_oauth_state_passes_ttl(self, configured_store, mock_redis):
        state = "ttl_state"
        await configured_store.save_oauth_state(state, ttl_seconds=600)

        call_kwargs = mock_redis.set.call_args.kwargs
        assert call_kwargs.get("ex") == 600


class TestCorruptedCiphertext:
    """Tests handling of corrupted ciphertext and decryption failures."""

    async def test_corrupted_ciphertext_raises_session_store_error(self, configured_store, mock_redis):
        session_id = "corrupted_session"
        key = configured_store._hash_session_id(session_id)
        # Store invalid/tampered ciphertext in Redis
        mock_redis._storage[key] = ("not-a-valid-fernet-token-garbage-bytes", 3600)

        with pytest.raises(SessionStoreError, match="Could not retrieve session"):
            await configured_store.get_session(session_id)

    async def test_differently_keyed_ciphertext_raises_session_store_error(self, configured_store, mock_redis):
        session_id = "wrong_key_session"
        key = configured_store._hash_session_id(session_id)

        # Encrypt with a DIFFERENT Fernet key
        other_key = Fernet.generate_key()
        other_fernet = Fernet(other_key)
        other_encrypted = other_fernet.encrypt(b'{"user": "alien"}').decode()
        mock_redis._storage[key] = (other_encrypted, 3600)

        with pytest.raises(SessionStoreError, match="Could not retrieve session"):
            await configured_store.get_session(session_id)


class TestRedisOperationFailures:
    """Tests handling of Redis I/O failures (network drop, timeout, outage)."""

    async def test_redis_set_failure_raises_session_store_error(self, configured_store, mock_redis):
        mock_redis.set.side_effect = ConnectionError("Redis connection dropped")
        with pytest.raises(SessionStoreError, match="Could not save session"):
            await configured_store.save_session("session_1", {"test": 1}, ttl_seconds=3600)

    async def test_redis_get_failure_raises_session_store_error(self, configured_store, mock_redis):
        mock_redis.get.side_effect = TimeoutError("Redis timeout")
        with pytest.raises(SessionStoreError, match="Could not retrieve session"):
            await configured_store.get_session("session_1")

    async def test_redis_delete_failure_raises_session_store_error(self, configured_store, mock_redis):
        mock_redis.delete.side_effect = Exception("Redis cluster unavailable")
        with pytest.raises(SessionStoreError, match="Could not delete session"):
            await configured_store.delete_session("session_1")

    async def test_oauth_state_save_failure_raises_session_store_error(self, configured_store, mock_redis):
        mock_redis.set.side_effect = ConnectionError("Redis unreachable")
        with pytest.raises(SessionStoreError, match="Could not save OAuth state"):
            await configured_store.save_oauth_state("state_val", ttl_seconds=600)

    async def test_oauth_state_consume_failure_raises_session_store_error(self, configured_store, mock_redis):
        mock_redis.delete.side_effect = ConnectionError("Redis unreachable")
        with pytest.raises(SessionStoreError, match="Could not consume OAuth state"):
            await configured_store.consume_oauth_state("state_val")


class TestSessionExpiry:
    """Tests verifying session expiry behavior."""

    async def test_session_returns_none_when_redis_key_absent(self, configured_store):
        """When Redis has evicted the key or it does not exist, get_session returns None."""
        result = await configured_store.get_session("nonexistent_or_expired_key")
        assert result is None

    async def test_session_expires_via_payload_timestamp(self, configured_store, mock_redis):
        """When the session payload timestamp is in the past, get_session returns None and deletes key."""
        session_id = "expired_session"
        expired_data = {
            "user": {"login": "testuser"},
            "access_token": "token",
            "expires_at": time.time() - 60,  # Expired 60s ago
        }
        await configured_store.save_session(session_id, expired_data, ttl_seconds=3600)

        # Retrieval should identify it as expired and return None
        result = await configured_store.get_session(session_id)
        assert result is None

        # Key should have been cleaned up from Redis
        key = configured_store._hash_session_id(session_id)
        assert key not in mock_redis._storage

    async def test_valid_session_before_expiry_returns_data(self, configured_store):
        """When session has a future expires_at timestamp, get_session returns data."""
        session_id = "valid_session"
        valid_data = {
            "user": {"login": "testuser"},
            "access_token": "token",
            "expires_at": time.time() + 3600,
        }
        await configured_store.save_session(session_id, valid_data, ttl_seconds=3600)

        result = await configured_store.get_session(session_id)
        assert result is not None
        assert result["user"]["login"] == "testuser"


class TestSessionStoreLogging:
    """Tests verifying that sensitive session IDs and credentials are never logged."""

    async def test_expired_session_does_not_log_raw_session_id(self, configured_store, caplog):
        raw_session_id = "sensitive_raw_session_id_abc12345"
        raw_token = "gho_secret_access_token_xyz987"
        expired_data = {
            "user": {"login": "testuser"},
            "access_token": raw_token,
            "expires_at": time.time() - 60,
        }
        with caplog.at_level("INFO"):
            await configured_store.save_session(raw_session_id, expired_data, ttl_seconds=3600)
            res = await configured_store.get_session(raw_session_id)
            assert res is None
            await configured_store.delete_session(raw_session_id)

        assert "Session has expired based on payload timestamp" in caplog.text
        assert raw_session_id not in caplog.text
        assert raw_token not in caplog.text

