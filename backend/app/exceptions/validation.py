"""
Input validation exceptions.
"""

from app.exceptions.base import PRInsightError


class InvalidPRURLError(PRInsightError):
    """Raised when a provided Pull Request URL does not match the expected format."""

    def __init__(self, url: str) -> None:
        super().__init__(
            message=f"Invalid GitHub Pull Request URL: '{url}'. "
            f"Expected format: https://github.com/{{owner}}/{{repo}}/pull/{{number}}",
            code="INVALID_PR_URL",
        )
        self.url = url
