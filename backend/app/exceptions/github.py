"""
GitHub API-specific exceptions.

Each exception maps to a specific failure mode of the GitHub REST API
and carries enough context for the centralized handler to produce
a meaningful error response.
"""

from app.exceptions.base import PRInsightError


class GitHubError(PRInsightError):
    """Base exception for all GitHub API failures."""

    def __init__(
        self, message: str = "GitHub API error.", code: str = "GITHUB_API_ERROR"
    ) -> None:
        super().__init__(message=message, code=code)


class GitHubNotFoundError(GitHubError):
    """Raised when a repository or pull request does not exist on GitHub."""

    def __init__(self, resource: str = "resource") -> None:
        super().__init__(
            message=f"The requested {resource} was not found on GitHub.",
            code="PR_NOT_FOUND",
        )


class GitHubRateLimitError(GitHubError):
    """Raised when the GitHub API rate limit has been exceeded."""

    def __init__(self, reset_at: str | None = None) -> None:
        reset_info = f" Rate limit resets at {reset_at}." if reset_at else ""
        super().__init__(
            message=f"GitHub API rate limit exceeded.{reset_info}",
            code="RATE_LIMIT_EXCEEDED",
        )
        self.reset_at = reset_at


class GitHubAuthenticationError(GitHubError):
    """Raised when the GitHub token is invalid or expired."""

    def __init__(self) -> None:
        super().__init__(
            message="GitHub authentication failed. The server's GitHub credentials are invalid or expired.",
            code="GITHUB_AUTH_ERROR",
        )


class GitHubAPIError(GitHubError):
    """Raised when GitHub returns an unexpected error (5xx, malformed response, etc.)."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        detail_info = f" Detail: {detail}" if detail else ""
        super().__init__(
            message=f"GitHub API returned an unexpected error (HTTP {status_code}).{detail_info}",
            code="GITHUB_API_ERROR",
        )
        self.status_code = status_code
