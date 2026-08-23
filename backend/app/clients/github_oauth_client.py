"""
GitHub OAuth client.

Handles the OAuth token exchange and user profile retrieval.
This is separate from the main GitHubClient, which handles
GitHub REST API calls using the service token (GITHUB_TOKEN).

This client handles:
    1. Exchanging an authorization code for an access token.
    2. Fetching the authenticated user's GitHub profile.
"""

import logging

import httpx

from app.core.config import Settings
from app.core.constants import GITHUB_OAUTH_TOKEN_URL, GITHUB_OAUTH_USER_URL
from app.exceptions.auth import OAuthError

logger = logging.getLogger(__name__)


class GitHubOAuthClient:
    """
    Async client for GitHub OAuth operations.

    Manages its own HTTPX AsyncClient lifecycle. Must be explicitly
    closed via close() during application shutdown.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout=30.0))

    async def close(self) -> None:
        """Close the underlying HTTPX client."""
        await self._client.aclose()

    async def exchange_code_for_token(self, code: str) -> str:
        """
        Exchange an OAuth authorization code for a GitHub access token.

        POST https://github.com/login/oauth/access_token

        Returns the access token string.
        Raises OAuthError if the exchange fails.
        """
        try:
            response = await self._client.post(
                GITHUB_OAUTH_TOKEN_URL,
                data={
                    "client_id": self._settings.GITHUB_OAUTH_CLIENT_ID,
                    "client_secret": self._settings.GITHUB_OAUTH_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": self._settings.GITHUB_OAUTH_REDIRECT_URI,
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                logger.error("GitHub OAuth token exchange failed with HTTP %d", response.status_code)
                raise OAuthError("Failed to exchange authorization code with GitHub.")

            data = response.json()

            if "error" in data:
                error_desc = data.get("error_description", data["error"])
                logger.error("GitHub OAuth token exchange error: %s", error_desc)
                raise OAuthError(f"GitHub OAuth error: {error_desc}")

            access_token = data.get("access_token")
            if not access_token:
                raise OAuthError("GitHub did not return an access token.")

            return access_token

        except httpx.HTTPError as exc:
            logger.error("Network error during OAuth token exchange: %s", type(exc).__name__)
            raise OAuthError("Failed to communicate with GitHub during authentication.") from exc

    async def get_user_profile(self, access_token: str) -> dict:
        """
        Fetch the authenticated user's GitHub profile.

        GET https://api.github.com/user

        Returns a dict with user profile fields.
        Raises OAuthError if the request fails.
        """
        try:
            response = await self._client.get(
                GITHUB_OAUTH_USER_URL,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "Authorization": f"Bearer {access_token}",
                },
            )

            if response.status_code != 200:
                logger.error("GitHub user profile request failed with HTTP %d", response.status_code)
                raise OAuthError("Failed to fetch GitHub user profile.")

            return response.json()

        except httpx.HTTPError as exc:
            logger.error("Network error fetching GitHub user profile: %s", type(exc).__name__)
            raise OAuthError("Failed to communicate with GitHub during authentication.") from exc
