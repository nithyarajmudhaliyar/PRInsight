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

class SessionStore:
    def __init__(self, redis_url: str, redis_token: str, encryption_key: str):
        self.redis = Redis(url=redis_url, token=redis_token) if redis_url and redis_token else None
        
        if encryption_key:
            try:
                self.fernet = Fernet(encryption_key.encode())
            except Exception as e:
                logger.error("Invalid OAUTH_TOKEN_ENCRYPTION_KEY: %s", e)
                self.fernet = None
        else:
            self.fernet = None

    def is_configured(self) -> bool:
        """Check if both Redis and Encryption key are properly configured."""
        return bool(self.redis and self.fernet)

    def _hash_session_id(self, session_id: str) -> str:
        """Hash the session ID to use as the Redis key, preventing session ID leakage in the DB."""
        return f"session:{hashlib.sha256(session_id.encode()).hexdigest()}"

    async def save_session(self, session_id: str, session_data: dict, ttl_seconds: int) -> None:
        """Encrypt and save the session data to Redis."""
        if not self.is_configured():
            logger.warning("Session store not configured, session not saved.")
            return

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
            return None
            
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
            return
            
        try:
            key = self._hash_session_id(session_id)
            await self.redis.delete(key)
        except Exception as e:
            logger.error("Failed to delete session from Redis: %s", e)
            raise SessionStoreError("Could not delete session") from e
