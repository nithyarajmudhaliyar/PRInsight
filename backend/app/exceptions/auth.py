"""
Authentication-specific exceptions.

Each exception maps to a specific failure mode of the OAuth flow
and carries enough context for the centralized handler to produce
a meaningful error response.
"""

from app.exceptions.base import PRInsightError


class AuthenticationError(PRInsightError):
    """Raised when a request requires authentication but the user is not authenticated."""

    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(message=message, code="AUTH_ERROR")


class OAuthError(PRInsightError):
    """Raised when the OAuth flow encounters an error (invalid state, missing code, etc.)."""

    def __init__(self, message: str = "OAuth authentication failed.") -> None:
        super().__init__(message=message, code="OAUTH_ERROR")


class OAuthNotConfiguredError(PRInsightError):
    """Raised when OAuth is attempted but client credentials are not configured."""

    def __init__(self) -> None:
        super().__init__(
            message="GitHub OAuth is not configured. Set GITHUB_OAUTH_CLIENT_ID and GITHUB_OAUTH_CLIENT_SECRET.",
            code="OAUTH_NOT_CONFIGURED",
        )
