"""
Authentication response models.

These models define the JSON shape returned by auth endpoints.
"""

from pydantic import BaseModel


class AuthUser(BaseModel):
    """Authenticated user's GitHub profile information."""

    id: int
    login: str
    name: str | None = None
    avatar_url: str | None = None


class AuthUserResponse(BaseModel):
    """Response model for GET /api/v1/auth/me."""

    status: str = "success"
    data: AuthUser


class LogoutResponse(BaseModel):
    """Response model for POST /api/v1/auth/logout."""

    status: str = "success"
    message: str = "Logged out successfully."
