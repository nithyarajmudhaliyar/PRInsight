"""
Session storage service using Upstash Redis.
Stores OAuth access tokens securely encrypted via Fernet.
"""

import json
import logging
import hashlib
from typing import Any

from cryptography.fernet import Fernet
from upstash_redis.asyncio import Redis

logger = logging.getLogger(__name__)

class SessionStoreError(Exception):
    """Base exception for session store errors."""
    pass


class SessionStoreConfigurationError(SessionStoreError):
    """Raised when SessionStore is missing required configuration or has invalid configuration."""
    pass


class SessionStore:
    def __init__(self, redis_url: str, redis_token: str, encryption_key: str):
        self._config_error: str | None = None

        if not redis_url or not redis_token:
            self.redis = None
            self._config_error = "Redis URL or token is missing"
        else:
            self.redis = Redis(url=redis_url, token=redis_token)

        if not encryption_key:
            self.fernet = None
            if not self._config_error:
                self._config_error = "OAUTH_TOKEN_ENCRYPTION_KEY is missing"
        else:
            try:
                key_bytes = encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
                self.fernet = Fernet(key_bytes)
            except Exception as e:
                logger.error("Invalid OAUTH_TOKEN_ENCRYPTION_KEY: %s", e)
                self.fernet = None
                if not self._config_error:
                    self._config_error = f"Invalid OAUTH_TOKEN_ENCRYPTION_KEY: {e}"

    def is_configured(self) -> bool:
        """Check if both Redis and Encryption key are properly configured."""
        return bool(self.redis and self.fernet)

    def _hash_session_id(self, session_id: str) -> str:
        """Hash the session ID to use as the Redis key, preventing session ID leakage in the DB."""
        return f"session:{hashlib.sha256(session_id.encode()).hexdigest()}"

    def _hash_oauth_state(self, state: str) -> str:
        """Hash the OAuth state parameter to use as the Redis key."""
        return f"oauth_state:{hashlib.sha256(state.encode()).hexdigest()}"

    async def save_oauth_state(self, state: str, ttl_seconds: int) -> None:
        """Save OAuth CSRF state parameter to Redis with TTL."""
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Failed to save OAuth state: %s", msg)
            raise SessionStoreConfigurationError(msg)

        try:
            key = self._hash_oauth_state(state)
            await self.redis.set(key, "1", ex=ttl_seconds)
        except Exception as e:
            logger.error("Failed to save OAuth state to Redis: %s", e)
            raise SessionStoreError("Could not save OAuth state") from e

    async def consume_oauth_state(self, state: str) -> bool:
        """
        Validate and atomically delete an OAuth state from Redis.
        Returns True if the state was valid and successfully consumed, False otherwise.
        """
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Failed to consume OAuth state: %s", msg)
            raise SessionStoreConfigurationError(msg)

        try:
            key = self._hash_oauth_state(state)
            res = await self.redis.delete(key)
            return bool(res and int(res) > 0)
        except Exception as e:
            logger.error("Failed to consume OAuth state from Redis: %s", e)
            raise SessionStoreError("Could not consume OAuth state") from e

    async def save_session(self, session_id: str, session_data: dict, ttl_seconds: int) -> None:
        """Encrypt and save the session data to Redis."""
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Failed to save session: %s", msg)
            raise SessionStoreConfigurationError(msg)

        try:
            payload = json.dumps(session_data).encode()
            encrypted_payload = self.fernet.encrypt(payload).decode()
            
            key = self._hash_session_id(session_id)
            await self.redis.set(key, encrypted_payload, ex=ttl_seconds)
        except Exception as e:
            logger.error("Failed to save session to Redis: %s", e)
            raise SessionStoreError("Could not save session") from e

    async def get_session(self, session_id: str) -> dict | None:
        """Retrieve and decrypt the session data from Redis."""
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Failed to retrieve session: %s", msg)
            raise SessionStoreConfigurationError(msg)
            
        try:
            key = self._hash_session_id(session_id)
            encrypted_payload = await self.redis.get(key)
            if not encrypted_payload:
                return None
                
            payload = self.fernet.decrypt(encrypted_payload.encode()).decode()
            return json.loads(payload)
        except Exception as e:
            logger.error("Failed to retrieve or decrypt session from Redis: %s", e)
            raise SessionStoreError("Could not retrieve session") from e

    async def delete_session(self, session_id: str) -> None:
        """Delete the session from Redis."""
        if not self.is_configured():
            msg = self._config_error or "Session store is not configured."
            logger.error("Failed to delete session: %s", msg)
            raise SessionStoreConfigurationError(msg)
            
        try:
            key = self._hash_session_id(session_id)
            await self.redis.delete(key)
        except Exception as e:
            logger.error("Failed to delete session from Redis: %s", e)
            raise SessionStoreError("Could not delete session") from e
