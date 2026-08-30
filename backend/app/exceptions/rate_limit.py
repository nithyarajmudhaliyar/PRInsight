"""
Rate limiting exceptions.

Raised when a client exceeds their allocated request rate.
"""

from app.exceptions.base import PRInsightError


class RateLimitExceededError(PRInsightError):
    """Raised when a client exceeds their per-IP or per-user rate limit."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(
            message=f"Rate limit exceeded. Please try again in {retry_after} seconds.",
            code="RATE_LIMIT_EXCEEDED",
        )
        self.retry_after = retry_after
