"""
Security configuration for PRInsight.

MVP: CORS middleware configuration.

Future additions (in this file):
    - Rate limiting middleware (slowapi or custom).
    - JWT verification middleware for GitHub OAuth.
    - Request size limits.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings


def configure_cors(app: FastAPI, settings: Settings) -> None:
    """
    Attach CORS middleware to the FastAPI application.

    Allowed origins are configured via the CORS_ORIGINS setting,
    which defaults to the Vite dev server (http://localhost:5173).
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
