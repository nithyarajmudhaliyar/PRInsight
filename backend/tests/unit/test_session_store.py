"""
Unit tests for SessionStore configuration and basic failure modes.
"""

import pytest
from cryptography.fernet import Fernet

from app.services.session_store import (
    SessionStore,
    SessionStoreConfigurationError,
)


@pytest.fixture
def valid_fernet_key() -> str:
    return Fernet.generate_key().decode()


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

