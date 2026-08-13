"""
Shared enums, base models, and the error envelope used across all schemas.
"""

from enum import Enum

from pydantic import BaseModel


class RiskLevel(str, Enum):
    """Risk classification for a conflicting Pull Request."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ErrorDetail(BaseModel):
    """Structured error information returned inside the error envelope."""

    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    """
    Consistent error envelope returned by all error handlers.

    Every error response from the API follows this shape, enabling
    the frontend to use error.code for conditional logic and
    error.message for user-facing display.
    """

    status: str = "error"
    error: ErrorDetail
