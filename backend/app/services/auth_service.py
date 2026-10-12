"""
Authentication service — session management and OAuth orchestration.

Manages the OAuth flow lifecycle:
    1. Generate GitHub OAuth authorization URLs with CSRF state tokens.
    2. Handle OAuth callbacks — exchange code, fetch profile, create session.
    3. Session CRUD — create, read, delete.

Sessions are stored in-memory (same approach as TTLCache).
This means sessions are lost on server restart, which is acceptable
for development. A persistent store can be added later.

Access tokens are stored server-side only — never sent to the frontend.
"""

import logging
import secrets
import time
import urllib.parse

from app.clients.github_oauth_client import GitHubOAuthClient
from app.core.config import Settings
from app.core.constants import (
    GITHUB_OAUTH_AUTHORIZE_URL,
    OAUTH_STATE_TTL_SECONDS,
)
from app.exceptions.auth import AuthenticationError, OAuthError, OAuthNotConfiguredError
from app.services.session_store import SessionStore, SessionStoreError

logger = logging.getLogger(__name__)


class AuthService:
    """
    Manages GitHub OAuth flow and user sessions.

    Attributes:
        _oauth_client: GitHubOAuthClient for token exchange and profile fetching.
        _settings: Application settings.
        _session_store: Persistent Redis-backed session store.
    """

    def __init__(self, oauth_client: GitHubOAuthClient, settings: Settings) -> None:
        self._oauth_client = oauth_client
        self._settings = settings
        self._session_store = SessionStore(
            redis_url=settings.UPSTASH_REDIS_REST_URL,
            redis_token=settings.UPSTASH_REDIS_REST_TOKEN,
            encryption_key=settings.OAUTH_TOKEN_ENCRYPTION_KEY,
        )

    def _ensure_oauth_configured(self) -> None:
        """Raise OAuthNotConfiguredError if OAuth credentials are missing."""
        if not self._settings.GITHUB_OAUTH_CLIENT_ID or not self._settings.GITHUB_OAUTH_CLIENT_SECRET:
            raise OAuthNotConfiguredError()

    async def create_login_url(self) -> tuple[str, str]:
        """
        Generate a GitHub OAuth authorization URL with a random state parameter.

        The state parameter is persisted to Redis with TTL to support serverless
        deployments where login and callback execute on different instances.

        Returns:
            (authorization_url, state) tuple.

        Raises:
            OAuthNotConfiguredError: If OAuth client credentials are not set.
            OAuthError: If state cannot be stored.
        """
        self._ensure_oauth_configured()

        state = secrets.token_urlsafe(32)
        try:
            await self._session_store.save_oauth_state(
                state=state,
                ttl_seconds=OAUTH_STATE_TTL_SECONDS,
            )
        except SessionStoreError as e:
            logger.error("Failed to persist OAuth state: %s", e)
            raise OAuthError("Failed to initiate OAuth login.") from e

        params = urllib.parse.urlencode({
            "client_id": self._settings.GITHUB_OAUTH_CLIENT_ID,
            "redirect_uri": self._settings.GITHUB_OAUTH_REDIRECT_URI,
            "scope": "read:user",
            "state": state,
        })

        authorization_url = f"{GITHUB_OAUTH_AUTHORIZE_URL}?{params}"
        return authorization_url, state

    async def validate_state(self, state: str) -> None:
        """
        Validate and consume an OAuth state parameter.

        The state is single-use: it is deleted from persistent storage after
        validation to prevent replay attacks across serverless instances.

        Raises:
            OAuthError: If state is missing, invalid, or expired.
        """
        if not state:
            raise OAuthError("Missing OAuth state parameter.")

        try:
            valid = await self._session_store.consume_oauth_state(state)
        except SessionStoreError as e:
            logger.error("Session store error validating state: %s", e)
            raise OAuthError("Failed to validate OAuth state.") from e

        if not valid:
            raise OAuthError("Invalid or expired OAuth state parameter.")

    async def handle_callback(self, code: str, state: str) -> str:
        """
        Handle the OAuth callback — exchange code, fetch profile, create session.

        Args:
            code: The authorization code from GitHub.
            state: The state parameter for CSRF validation.

        Returns:
            session_id: The newly created session ID.

        Raises:
            OAuthError: If code or state is invalid.
            OAuthNotConfiguredError: If OAuth is not configured.
        """
        self._ensure_oauth_configured()

        if not code:
            raise OAuthError("Missing authorization code.")

        await self.validate_state(state)

        # Exchange the authorization code for an access token
        access_token = await self._oauth_client.exchange_code_for_token(code)

        # Fetch the authenticated user's GitHub profile
        profile = await self._oauth_client.get_user_profile(access_token)

        # Create a session
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        
        session_data = {
            "user": {
                "id": profile.get("id"),
                "login": profile.get("login"),
                "name": profile.get("name"),
                "avatar_url": profile.get("avatar_url"),
            },
            "access_token": access_token,
            "created_at": now,
        }

        try:
            await self._session_store.save_session(
                session_id, 
                session_data, 
                ttl_seconds=self._settings.SESSION_TTL_SECONDS
            )
        except SessionStoreError as e:
            logger.error("Failed to persist session: %s", e)
            raise OAuthError("Internal error creating session.") from e

        logger.info("Session created for GitHub user: %s", profile.get("login"))
        return session_id

    async def get_current_user(self, session_id: str | None) -> dict:
        """
        Look up the authenticated user from a session ID.

        Args:
            session_id: The session ID from the cookie.

        Returns:
            User data dict with id, login, name, avatar_url.

        Raises:
            AuthenticationError: If no session, session expired, or storage error.
        """
        if not session_id:
            raise AuthenticationError()

        try:
            session = await self._session_store.get_session(session_id)
        except SessionStoreError as e:
            logger.error("Session store error during get_current_user: %s", e)
            raise AuthenticationError("Session verification failed.") from e

        if session is None:
            raise AuthenticationError()

        # We rely on Redis TTL for expiration, so if it exists, it's valid.
        return session["user"]

    async def logout(self, session_id: str | None) -> None:
        """
        Remove a session, effectively logging out the user.

        Args:
            session_id: The session ID from the cookie.
        """
        if session_id:
            try:
                await self._session_store.delete_session(session_id)
            except SessionStoreError as e:
                logger.error("Session store error during logout: %s", e)
                raise

