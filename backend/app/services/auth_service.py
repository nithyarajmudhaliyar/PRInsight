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

logger = logging.getLogger(__name__)


class AuthService:
    """
    Manages GitHub OAuth flow and user sessions.

    Attributes:
        _oauth_client: GitHubOAuthClient for token exchange and profile fetching.
        _settings: Application settings.
        _sessions: In-memory session store {session_id: session_data}.
        _oauth_states: In-memory CSRF state store {state: expiry_timestamp}.
    """

    def __init__(self, oauth_client: GitHubOAuthClient, settings: Settings) -> None:
        self._oauth_client = oauth_client
        self._settings = settings
        self._sessions: dict[str, dict] = {}
        self._oauth_states: dict[str, float] = {}

    def _ensure_oauth_configured(self) -> None:
        """Raise OAuthNotConfiguredError if OAuth credentials are missing."""
        if not self._settings.GITHUB_OAUTH_CLIENT_ID or not self._settings.GITHUB_OAUTH_CLIENT_SECRET:
            raise OAuthNotConfiguredError()

    def create_login_url(self) -> tuple[str, str]:
        """
        Generate a GitHub OAuth authorization URL with a random state parameter.

        Returns:
            (authorization_url, state) tuple.

        Raises:
            OAuthNotConfiguredError: If OAuth client credentials are not set.
        """
        self._ensure_oauth_configured()

        state = secrets.token_urlsafe(32)
        self._oauth_states[state] = time.time() + OAUTH_STATE_TTL_SECONDS

        # Clean up expired states (simple housekeeping)
        now = time.time()
        expired = [s for s, exp in self._oauth_states.items() if exp < now]
        for s in expired:
            del self._oauth_states[s]

        params = urllib.parse.urlencode({
            "client_id": self._settings.GITHUB_OAUTH_CLIENT_ID,
            "redirect_uri": self._settings.GITHUB_OAUTH_REDIRECT_URI,
            "scope": "read:user",
            "state": state,
        })

        authorization_url = f"{GITHUB_OAUTH_AUTHORIZE_URL}?{params}"
        return authorization_url, state

    def validate_state(self, state: str) -> None:
        """
        Validate and consume an OAuth state parameter.

        The state is single-use: it is deleted after validation to prevent replay.

        Raises:
            OAuthError: If state is missing, invalid, or expired.
        """
        if not state:
            raise OAuthError("Missing OAuth state parameter.")

        expiry = self._oauth_states.pop(state, None)
        if expiry is None:
            raise OAuthError("Invalid OAuth state parameter.")

        if time.time() > expiry:
            raise OAuthError("OAuth state parameter has expired. Please try again.")

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

        self.validate_state(state)

        # Exchange the authorization code for an access token
        access_token = await self._oauth_client.exchange_code_for_token(code)

        # Fetch the authenticated user's GitHub profile
        profile = await self._oauth_client.get_user_profile(access_token)

        # Create a session
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        self._sessions[session_id] = {
            "user": {
                "id": profile.get("id"),
                "login": profile.get("login"),
                "name": profile.get("name"),
                "avatar_url": profile.get("avatar_url"),
            },
            "access_token": access_token,
            "created_at": now,
            "expires_at": now + self._settings.SESSION_TTL_SECONDS,
        }

        logger.info("Session created for GitHub user: %s", profile.get("login"))
        return session_id

    def get_current_user(self, session_id: str | None) -> dict:
        """
        Look up the authenticated user from a session ID.

        Args:
            session_id: The session ID from the cookie.

        Returns:
            User data dict with id, login, name, avatar_url.

        Raises:
            AuthenticationError: If no session or session is expired.
        """
        if not session_id:
            raise AuthenticationError()

        session = self._sessions.get(session_id)
        if session is None:
            raise AuthenticationError()

        if time.time() > session["expires_at"]:
            # Session expired — clean it up
            del self._sessions[session_id]
            raise AuthenticationError("Session has expired. Please sign in again.")

        return session["user"]

    def logout(self, session_id: str | None) -> None:
        """
        Remove a session, effectively logging out the user.

        Args:
            session_id: The session ID from the cookie.
        """
        if session_id and session_id in self._sessions:
            logger.info(
                "Session removed for user: %s",
                self._sessions[session_id]["user"].get("login"),
            )
            del self._sessions[session_id]
