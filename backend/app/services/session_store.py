"""
Session storage service using Neon PostgreSQL.
Stores OAuth access tokens securely encrypted via Fernet.
"""

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import logging
import time
from typing import Any

from cryptography.fernet import Fernet
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_hash VARCHAR(64) PRIMARY KEY,
    encrypted_payload TEXT NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at);

CREATE TABLE IF NOT EXISTS oauth_states (
    state_hash VARCHAR(64) PRIMARY KEY,
    expires_at DOUBLE PRECISION NOT NULL,
    created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oauth_states_expires_at ON oauth_states (expires_at);
"""


class SessionStoreError(Exception):
    """Base exception for session store errors."""
    pass


class SessionStoreConfigurationError(SessionStoreError):
    """Raised when SessionStore is missing required configuration or has invalid configuration."""
    pass


class SessionStore:
    def __init__(
        self,
        database_url: str,
        encryption_key: str,
        pool: Any | None = None,
    ):
        self._config_error: str | None = None
        self.database_url = (database_url or "").strip()
        self.fernet: Fernet | None = None
        self._pool = pool
        self._schema_initialized = False
        self._schema_lock = asyncio.Lock()
        self._last_cleanup_time: float = 0.0

        if not self.database_url:
            self._config_error = "DATABASE_URL is missing"

        if not encryption_key:
            if not self._config_error:
                self._config_error = "OAUTH_TOKEN_ENCRYPTION_KEY is missing"
        else:
            try:
                key_bytes = encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
                self.fernet = Fernet(key_bytes)
            except Exception as e:
                logger.error("Invalid OAUTH_TOKEN_ENCRYPTION_KEY: %s", e)
                if not self._config_error:
                    self._config_error = f"Invalid OAUTH_TOKEN_ENCRYPTION_KEY: {e}"

    def is_configured(self) -> bool:
        """Check if both database connection and encryption key are properly configured."""
        return bool(self.database_url and self.fernet)

    def _create_pool(self) -> AsyncConnectionPool:
        """Create bounded connection pool suitable for serverless Vercel with Neon."""
        return AsyncConnectionPool(
            conninfo=self.database_url,
            min_size=0,
            max_size=3,
            timeout=10.0,
            max_idle=60.0,
            open=False,
            kwargs={"autocommit": True},
        )

    @asynccontextmanager
    async def connection(self):
        """Yield an async PostgreSQL connection from the bounded pool."""
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Database operation failed: %s", msg)
            raise SessionStoreConfigurationError(msg)

        if self._pool is None:
            self._pool = self._create_pool()

        if hasattr(self._pool, "closed") and self._pool.closed:
            try:
                await self._pool.open()
            except Exception as e:
                logger.error("Failed to open database connection pool: %s", e)
                raise SessionStoreError("Could not connect to database") from e

        try:
            async with self._pool.connection() as conn:
                yield conn
        except SessionStoreError:
            raise
        except Exception as e:
            logger.error("Database connection or query failure: %s", e)
            raise SessionStoreError(f"Database operation failed: {e}") from e

    async def ensure_schema(self) -> None:
        """Idempotently create tables and indexes if not already initialized."""
        if self._schema_initialized:
            return

        async with self._schema_lock:
            if self._schema_initialized:
                return

            try:
                async with self.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(SCHEMA_SQL)
                self._schema_initialized = True
            except SessionStoreError:
                raise
            except Exception as e:
                logger.error("Failed to initialize database schema: %s", e)
                raise SessionStoreError("Could not initialize database schema") from e

    async def cleanup_expired(self, force: bool = False) -> None:
        """
        Delete expired sessions and OAuth states.
        Throttled to run at most once every 5 minutes unless force is True.
        """
        now = time.time()
        if not force and (now - self._last_cleanup_time < 300):
            return

        self._last_cleanup_time = now
        try:
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM sessions WHERE expires_at <= %s;",
                        (now,),
                    )
                    await cur.execute(
                        "DELETE FROM oauth_states WHERE expires_at <= %s;",
                        (now,),
                    )
        except Exception as e:
            # Non-fatal opportunistic cleanup
            logger.warning("Opportunistic cleanup of expired records failed: %s", e)

    async def close(self) -> None:
        """Close connection pool on application shutdown."""
        if self._pool is not None and hasattr(self._pool, "close"):
            try:
                await self._pool.close()
            except Exception:
                pass

    def _hash_session_id(self, session_id: str) -> str:
        """Hash the session ID to use as the database key, preventing session ID leakage."""
        return hashlib.sha256(session_id.encode()).hexdigest()

    def _hash_oauth_state(self, state: str) -> str:
        """Hash the OAuth state parameter to use as the database key."""
        return hashlib.sha256(state.encode()).hexdigest()

    async def save_oauth_state(self, state: str, ttl_seconds: int) -> None:
        """Save OAuth CSRF state parameter to PostgreSQL with TTL."""
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Failed to save OAuth state: %s", msg)
            raise SessionStoreConfigurationError(msg)

        await self.ensure_schema()
        now = time.time()
        expires_at = now + ttl_seconds
        state_hash = self._hash_oauth_state(state)

        try:
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO oauth_states (state_hash, expires_at, created_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (state_hash) DO UPDATE
                        SET expires_at = EXCLUDED.expires_at,
                            created_at = EXCLUDED.created_at;
                        """,
                        (state_hash, expires_at, now),
                    )
            await self.cleanup_expired()
        except SessionStoreError:
            raise
        except Exception as e:
            logger.error("Failed to save OAuth state to PostgreSQL: %s", e)
            raise SessionStoreError("Could not save OAuth state") from e

    async def consume_oauth_state(self, state: str) -> bool:
        """
        Validate and atomically delete an OAuth state from PostgreSQL.
        Returns True if the state was valid, unexpired, and successfully consumed; False otherwise.
        """
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Failed to consume OAuth state: %s", msg)
            raise SessionStoreConfigurationError(msg)

        await self.ensure_schema()
        now = time.time()
        state_hash = self._hash_oauth_state(state)

        try:
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        DELETE FROM oauth_states
                        WHERE state_hash = %s AND expires_at > %s
                        RETURNING state_hash;
                        """,
                        (state_hash, now),
                    )
                    row = await cur.fetchone()
                    return bool(row is not None)
        except SessionStoreError:
            raise
        except Exception as e:
            logger.error("Failed to consume OAuth state from PostgreSQL: %s", e)
            raise SessionStoreError("Could not consume OAuth state") from e

    async def save_session(self, session_id: str, session_data: dict, ttl_seconds: int) -> None:
        """Encrypt and save the session data to PostgreSQL."""
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Failed to save session: %s", msg)
            raise SessionStoreConfigurationError(msg)

        await self.ensure_schema()
        now = time.time()
        expires_at = now + ttl_seconds if ttl_seconds else now + 86400
        payload_data = dict(session_data)
        if "expires_at" not in payload_data and ttl_seconds:
            payload_data["expires_at"] = expires_at

        try:
            payload = json.dumps(payload_data).encode()
            encrypted_payload = self.fernet.encrypt(payload).decode()
            session_hash = self._hash_session_id(session_id)

            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO sessions (session_hash, encrypted_payload, expires_at, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (session_hash) DO UPDATE
                        SET encrypted_payload = EXCLUDED.encrypted_payload,
                            expires_at = EXCLUDED.expires_at,
                            created_at = EXCLUDED.created_at;
                        """,
                        (session_hash, encrypted_payload, expires_at, now),
                    )
            await self.cleanup_expired()
        except SessionStoreError:
            raise
        except Exception as e:
            logger.error("Failed to save session to PostgreSQL: %s", e)
            raise SessionStoreError("Could not save session") from e

    async def get_session(self, session_id: str) -> dict | None:
        """Retrieve and decrypt the session data from PostgreSQL."""
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Failed to retrieve session: %s", msg)
            raise SessionStoreConfigurationError(msg)

        await self.ensure_schema()
        session_hash = self._hash_session_id(session_id)
        now = time.time()

        try:
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT encrypted_payload, expires_at FROM sessions WHERE session_hash = %s;",
                        (session_hash,),
                    )
                    row = await cur.fetchone()
                    if not row:
                        return None

                    encrypted_payload, expires_at = row[0], row[1]
                    if expires_at <= now:
                        logger.info("Session has expired based on payload timestamp")
                        try:
                            await cur.execute(
                                "DELETE FROM sessions WHERE session_hash = %s;",
                                (session_hash,),
                            )
                        except Exception:
                            pass
                        return None

            try:
                payload = self.fernet.decrypt(encrypted_payload.encode()).decode()
                data = json.loads(payload)
            except Exception as decrypt_err:
                logger.error("Failed to decrypt session payload: %s", decrypt_err)
                raise SessionStoreError("Could not retrieve session") from decrypt_err

            if "expires_at" in data and now > data["expires_at"]:
                logger.info("Session has expired based on payload timestamp")
                try:
                    async with self.connection() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(
                                "DELETE FROM sessions WHERE session_hash = %s;",
                                (session_hash,),
                            )
                except Exception:
                    pass
                return None

            return data
        except SessionStoreError:
            raise
        except Exception as e:
            logger.error("Failed to retrieve or decrypt session from PostgreSQL: %s", e)
            raise SessionStoreError("Could not retrieve session") from e

    async def delete_session(self, session_id: str) -> None:
        """Delete the session from PostgreSQL."""
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Failed to delete session: %s", msg)
            raise SessionStoreConfigurationError(msg)

        await self.ensure_schema()
        session_hash = self._hash_session_id(session_id)

        try:
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM sessions WHERE session_hash = %s;",
                        (session_hash,),
                    )
        except SessionStoreError:
            raise
        except Exception as e:
            logger.error("Failed to delete session from PostgreSQL: %s", e)
            raise SessionStoreError("Could not delete session") from e
