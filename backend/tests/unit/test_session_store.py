"""
Unit tests for SessionStore using Neon PostgreSQL.

Tests cover:
    - Configuration validation (missing/invalid config, fail closed)
    - Fernet encryption and decryption
    - Hashed database keys (preventing raw token/session leakage)
    - OAuth state creation, atomic single-use consumption, and expiration
    - Corrupted ciphertext and decryption failures
    - PostgreSQL connection and query failures
    - Session expiry and opportunistic cleanup
    - Caplog assertion that raw session IDs and credentials are never logged
    - Independent service instances sharing persistent storage abstraction
"""

from contextlib import asynccontextmanager
import hashlib
import json
import time
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
import psycopg

from app.services.session_store import (
    SessionStore,
    SessionStoreConfigurationError,
    SessionStoreError,
)


@pytest.fixture
def valid_fernet_key() -> str:
    return Fernet.generate_key().decode()


class MockCursor:
    def __init__(self, db: dict, fail_on_query: str | None = None):
        self.db = db
        self.fail_on_query = fail_on_query
        self._last_result = None

    async def execute(self, query: str, params=None):
        if self.fail_on_query and self.fail_on_query in query:
            raise psycopg.OperationalError(f"Simulated database error on {self.fail_on_query}")

        params = params or ()
        normalized = " ".join(query.strip().split())

        if "CREATE TABLE" in query or "CREATE INDEX" in query:
            return

        if "INSERT INTO oauth_states" in query:
            state_hash, expires_at, created_at = params
            self.db["oauth_states"][state_hash] = (expires_at, created_at)

        elif "DELETE FROM oauth_states WHERE state_hash = %s AND expires_at > %s RETURNING state_hash" in normalized:
            state_hash, now = params
            if state_hash in self.db["oauth_states"]:
                expires_at, _ = self.db["oauth_states"][state_hash]
                if expires_at > now:
                    del self.db["oauth_states"][state_hash]
                    self._last_result = (state_hash,)
                    return
            self._last_result = None

        elif "INSERT INTO sessions" in query:
            session_hash, encrypted_payload, expires_at, created_at = params
            self.db["sessions"][session_hash] = (encrypted_payload, expires_at, created_at)

        elif "SELECT encrypted_payload, expires_at FROM sessions WHERE session_hash = %s" in normalized:
            session_hash = params[0]
            if session_hash in self.db["sessions"]:
                enc, exp, _ = self.db["sessions"][session_hash]
                self._last_result = (enc, exp)
            else:
                self._last_result = None

        elif "DELETE FROM sessions WHERE session_hash = %s" in normalized:
            session_hash = params[0]
            self.db["sessions"].pop(session_hash, None)

        elif "DELETE FROM sessions WHERE expires_at <=" in query:
            now = params[0]
            to_del = [k for k, v in list(self.db["sessions"].items()) if v[1] <= now]
            for k in to_del:
                del self.db["sessions"][k]

        elif "DELETE FROM oauth_states WHERE expires_at <=" in query:
            now = params[0]
            to_del = [k for k, v in list(self.db["oauth_states"].items()) if v[0] <= now]
            for k in to_del:
                del self.db["oauth_states"][k]

    async def fetchone(self):
        res = self._last_result
        self._last_result = None
        return res

    async def fetchall(self):
        return []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockConnection:
    def __init__(self, db: dict, fail_on_query: str | None = None):
        self.db = db
        self.fail_on_query = fail_on_query

    def cursor(self):
        return MockCursor(self.db, fail_on_query=self.fail_on_query)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockConnectionPool:
    def __init__(self, db: dict | None = None):
        self.db = db if db is not None else {
            "sessions": {},
            "oauth_states": {},
        }
        self.closed = False
        self.fail_connect = False
        self.fail_query = None

    async def open(self):
        self.closed = False

    async def close(self):
        self.closed = True

    @asynccontextmanager
    async def connection(self):
        if self.fail_connect:
            raise psycopg.OperationalError("Could not connect to PostgreSQL server: connection refused")
        yield MockConnection(self.db, fail_on_query=self.fail_query)


@pytest.fixture
def mock_pool() -> MockConnectionPool:
    return MockConnectionPool()


@pytest.fixture
def configured_store(valid_fernet_key, mock_pool) -> SessionStore:
    """SessionStore with valid Fernet key and mock PostgreSQL connection pool."""
    store = SessionStore(
        database_url="postgresql://user:pass@ep-sample-pooler.neon.tech/neondb?sslmode=require",
        encryption_key=valid_fernet_key,
        pool=mock_pool,
    )
    return store


class TestSessionStoreConfiguration:
    """Tests for SessionStore configuration validation and fail-closed behavior."""

    def test_configured_when_all_params_valid(self, valid_fernet_key):
        store = SessionStore(
            database_url="postgresql://user:pass@ep-sample-pooler.neon.tech/neondb?sslmode=require",
            encryption_key=valid_fernet_key,
        )
        assert store.is_configured() is True
        assert store._config_error is None

    def test_unconfigured_when_database_url_missing(self, valid_fernet_key):
        store = SessionStore(
            database_url="",
            encryption_key=valid_fernet_key,
        )
        assert store.is_configured() is False
        assert "DATABASE_URL is missing" in store._config_error

    def test_unconfigured_when_encryption_key_missing(self):
        store = SessionStore(
            database_url="postgresql://user:pass@ep-sample-pooler.neon.tech/neondb?sslmode=require",
            encryption_key="",
        )
        assert store.is_configured() is False
        assert "OAUTH_TOKEN_ENCRYPTION_KEY is missing" in store._config_error

    def test_unconfigured_when_encryption_key_invalid(self):
        store = SessionStore(
            database_url="postgresql://user:pass@ep-sample-pooler.neon.tech/neondb?sslmode=require",
            encryption_key="invalid-not-base64-key",
        )
        assert store.is_configured() is False
        assert "Invalid OAUTH_TOKEN_ENCRYPTION_KEY" in store._config_error

    async def test_save_session_raises_when_database_url_missing(self, valid_fernet_key):
        store = SessionStore(
            database_url="",
            encryption_key=valid_fernet_key,
        )
        with pytest.raises(SessionStoreConfigurationError, match="DATABASE_URL is missing"):
            await store.save_session("session_123", {"user": "test"}, 3600)

    async def test_save_session_raises_when_encryption_key_missing(self):
        store = SessionStore(
            database_url="postgresql://user:pass@ep-sample-pooler.neon.tech/neondb?sslmode=require",
            encryption_key="",
        )
        with pytest.raises(SessionStoreConfigurationError, match="OAUTH_TOKEN_ENCRYPTION_KEY is missing"):
            await store.save_session("session_123", {"user": "test"}, 3600)

    async def test_save_session_raises_when_encryption_key_invalid(self):
        store = SessionStore(
            database_url="postgresql://user:pass@ep-sample-pooler.neon.tech/neondb?sslmode=require",
            encryption_key="not-a-fernet-key",
        )
        with pytest.raises(SessionStoreConfigurationError, match="Invalid OAUTH_TOKEN_ENCRYPTION_KEY"):
            await store.save_session("session_123", {"user": "test"}, 3600)

    async def test_get_session_raises_when_unconfigured(self):
        store = SessionStore(database_url="", encryption_key="")
        with pytest.raises(SessionStoreConfigurationError):
            await store.get_session("session_123")

    async def test_delete_session_raises_when_unconfigured(self):
        store = SessionStore(database_url="", encryption_key="")
        with pytest.raises(SessionStoreConfigurationError):
            await store.delete_session("session_123")

    async def test_save_oauth_state_raises_when_unconfigured(self):
        store = SessionStore(database_url="", encryption_key="")
        with pytest.raises(SessionStoreConfigurationError):
            await store.save_oauth_state("state_123", 600)

    async def test_consume_oauth_state_raises_when_unconfigured(self):
        store = SessionStore(database_url="", encryption_key="")
        with pytest.raises(SessionStoreConfigurationError):
            await store.consume_oauth_state("state_123")


class TestFernetEncryptionDecryption:
    """Tests verifying Fernet encryption and decryption behavior."""

    async def test_session_payload_is_encrypted_in_database(self, configured_store, mock_pool):
        session_id = "session_xyz_789"
        raw_data = {"user": {"login": "octocat"}, "access_token": "gho_secret_access_token"}
        await configured_store.save_session(session_id, raw_data, ttl_seconds=3600)

        hashed_key = configured_store._hash_session_id(session_id)
        assert hashed_key in mock_pool.db["sessions"]
        stored_ciphertext, expires_at, _ = mock_pool.db["sessions"][hashed_key]

        # Plaintext secrets must NOT appear in the database ciphertext
        assert "gho_secret_access_token" not in stored_ciphertext
        assert "octocat" not in stored_ciphertext

        # Ciphertext must decrypt correctly with Fernet
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


class TestHashedDatabaseKeys:
    """Tests verifying lookup keys are securely hashed with SHA-256."""

    async def test_session_key_is_sha256_hashed(self, configured_store, mock_pool):
        session_id = "my_sensitive_session_id"
        expected_hash = hashlib.sha256(session_id.encode()).hexdigest()

        await configured_store.save_session(session_id, {"data": 1}, ttl_seconds=3600)

        assert expected_hash in mock_pool.db["sessions"]
        assert session_id not in expected_hash
        assert len(expected_hash) == 64

    async def test_oauth_state_key_is_sha256_hashed(self, configured_store, mock_pool):
        state = "random_state_nonce"
        expected_hash = hashlib.sha256(state.encode()).hexdigest()

        await configured_store.save_oauth_state(state, ttl_seconds=600)

        assert expected_hash in mock_pool.db["oauth_states"]
        assert state not in expected_hash
        assert len(expected_hash) == 64


class TestOAuthStateAtomicity:
    """Tests verifying OAuth state creation, atomic single-use consumption, and expiry."""

    async def test_save_and_consume_oauth_state(self, configured_store):
        state = "single_use_state_xyz"
        await configured_store.save_oauth_state(state, ttl_seconds=600)

        # First consumption succeeds
        assert await configured_store.consume_oauth_state(state) is True
        # Second consumption fails (single-use)
        assert await configured_store.consume_oauth_state(state) is False

    async def test_consume_nonexistent_state_returns_false(self, configured_store):
        assert await configured_store.consume_oauth_state("nonexistent_state") is False

    async def test_consume_expired_state_returns_false(self, configured_store, mock_pool):
        state = "expired_state_abc"
        await configured_store.save_oauth_state(state, ttl_seconds=600)

        # Manually expire the state
        state_hash = configured_store._hash_oauth_state(state)
        mock_pool.db["oauth_states"][state_hash] = (time.time() - 10, time.time() - 610)

        assert await configured_store.consume_oauth_state(state) is False

    async def test_independent_instances_share_state(self, valid_fernet_key, mock_pool):
        instance_a = SessionStore(
            database_url="postgresql://user:pass@ep-sample-pooler.neon.tech/neondb?sslmode=require",
            encryption_key=valid_fernet_key,
            pool=mock_pool,
        )
        instance_b = SessionStore(
            database_url="postgresql://user:pass@ep-sample-pooler.neon.tech/neondb?sslmode=require",
            encryption_key=valid_fernet_key,
            pool=mock_pool,
        )

        state = "cross_instance_state_123"
        await instance_a.save_oauth_state(state, ttl_seconds=600)

        # Instance B consumes it
        assert await instance_b.consume_oauth_state(state) is True
        # Subsequent consumption by either fails
        assert await instance_a.consume_oauth_state(state) is False
        assert await instance_b.consume_oauth_state(state) is False


class TestCorruptedCiphertext:
    """Tests handling of corrupted ciphertext and decryption failures."""

    async def test_corrupted_ciphertext_raises_session_store_error(self, configured_store, mock_pool):
        session_id = "corrupted_session"
        key = configured_store._hash_session_id(session_id)
        mock_pool.db["sessions"][key] = ("not-a-valid-fernet-token-garbage-bytes", time.time() + 3600, time.time())

        with pytest.raises(SessionStoreError, match="Could not retrieve session"):
            await configured_store.get_session(session_id)

    async def test_differently_keyed_ciphertext_raises_session_store_error(self, configured_store, mock_pool):
        session_id = "wrong_key_session"
        key = configured_store._hash_session_id(session_id)

        other_key = Fernet.generate_key()
        other_fernet = Fernet(other_key)
        other_encrypted = other_fernet.encrypt(b'{"user": "alien"}').decode()
        mock_pool.db["sessions"][key] = (other_encrypted, time.time() + 3600, time.time())

        with pytest.raises(SessionStoreError, match="Could not retrieve session"):
            await configured_store.get_session(session_id)


class TestPostgresOperationFailures:
    """Tests handling of PostgreSQL connection and query failures."""

    async def test_connection_failure_raises_session_store_error(self, configured_store, mock_pool):
        mock_pool.fail_connect = True
        with pytest.raises(SessionStoreError, match="Database operation failed|Could not connect"):
            await configured_store.save_session("session_1", {"test": 1}, ttl_seconds=3600)

    async def test_query_failure_on_save_session_raises_session_store_error(self, configured_store, mock_pool):
        mock_pool.fail_query = "INSERT INTO sessions"
        with pytest.raises(SessionStoreError, match="Could not save session|Database operation failed"):
            await configured_store.save_session("session_1", {"test": 1}, ttl_seconds=3600)

    async def test_query_failure_on_get_session_raises_session_store_error(self, configured_store, mock_pool):
        mock_pool.fail_query = "SELECT encrypted_payload"
        with pytest.raises(SessionStoreError, match="Could not retrieve session|Database operation failed"):
            await configured_store.get_session("session_1")

    async def test_query_failure_on_delete_session_raises_session_store_error(self, configured_store, mock_pool):
        mock_pool.fail_query = "DELETE FROM sessions"
        with pytest.raises(SessionStoreError, match="Could not delete session|Database operation failed"):
            await configured_store.delete_session("session_1")

    async def test_query_failure_on_save_oauth_state_raises_session_store_error(self, configured_store, mock_pool):
        mock_pool.fail_query = "INSERT INTO oauth_states"
        with pytest.raises(SessionStoreError, match="Could not save OAuth state|Database operation failed"):
            await configured_store.save_oauth_state("state_val", ttl_seconds=600)

    async def test_query_failure_on_consume_oauth_state_raises_session_store_error(self, configured_store, mock_pool):
        mock_pool.fail_query = "DELETE FROM oauth_states"
        with pytest.raises(SessionStoreError, match="Could not consume OAuth state|Database operation failed"):
            await configured_store.consume_oauth_state("state_val")


class TestSessionExpiry:
    """Tests verifying session expiry and cleanup behavior."""

    async def test_session_returns_none_when_db_key_absent(self, configured_store):
        result = await configured_store.get_session("nonexistent_session_key")
        assert result is None

    async def test_session_expires_via_expires_at_column(self, configured_store, mock_pool):
        session_id = "expired_session"
        expired_data = {
            "user": {"login": "testuser"},
            "access_token": "token",
            "expires_at": time.time() - 60,
        }
        await configured_store.save_session(session_id, expired_data, ttl_seconds=3600)

        # Force column expires_at into past
        key = configured_store._hash_session_id(session_id)
        enc, _, created = mock_pool.db["sessions"][key]
        mock_pool.db["sessions"][key] = (enc, time.time() - 10, created)

        result = await configured_store.get_session(session_id)
        assert result is None
        # Cleaned up from database
        assert key not in mock_pool.db["sessions"]

    async def test_session_expires_via_payload_timestamp(self, configured_store, mock_pool):
        session_id = "expired_payload_session"
        expired_data = {
            "user": {"login": "testuser"},
            "access_token": "token",
            "expires_at": time.time() - 60,
        }
        # Save with payload timestamp expired but column timestamp in future
        await configured_store.save_session(session_id, expired_data, ttl_seconds=3600)

        result = await configured_store.get_session(session_id)
        assert result is None

        key = configured_store._hash_session_id(session_id)
        assert key not in mock_pool.db["sessions"]

    async def test_valid_session_before_expiry_returns_data(self, configured_store):
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

    async def test_cleanup_expired_removes_stale_records(self, configured_store, mock_pool):
        now = time.time()
        # Insert stale session and stale oauth state directly into mock DB
        mock_pool.db["sessions"]["stale_sess"] = ("enc", now - 100, now - 200)
        mock_pool.db["sessions"]["active_sess"] = ("enc", now + 1000, now)
        mock_pool.db["oauth_states"]["stale_state"] = (now - 100, now - 200)
        mock_pool.db["oauth_states"]["active_state"] = (now + 500, now)

        await configured_store.cleanup_expired(force=True)

        assert "stale_sess" not in mock_pool.db["sessions"]
        assert "active_sess" in mock_pool.db["sessions"]
        assert "stale_state" not in mock_pool.db["oauth_states"]
        assert "active_state" in mock_pool.db["oauth_states"]


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
