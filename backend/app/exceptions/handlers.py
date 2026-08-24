"""
Centralized FastAPI exception handlers.

All exception handlers are registered here and attached to the FastAPI
application in main.py. This is the single point where all errors converge,
ensuring:
    1. Consistent JSON error envelope for every failure.
    2. Every exception is logged.
    3. No raw stack traces leak to the client.
"""

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exceptions.auth import (
    AuthenticationError,
    OAuthError,
    OAuthNotConfiguredError,
)
from app.exceptions.base import PRInsightError
from app.exceptions.github import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from app.exceptions.validation import InvalidPRURLError

logger = logging.getLogger(__name__)


def _error_response(status_code: int, code: str, message: str, details: object = None) -> JSONResponse:
    """Build a consistent error JSON envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
        },
    )


async def _handle_invalid_pr_url(request: Request, exc: Exception) -> JSONResponse:
    err = cast(InvalidPRURLError, exc)
    logger.warning("Invalid PR URL: %s", err.url)
    return _error_response(400, err.code, err.message)


async def _handle_github_not_found(request: Request, exc: Exception) -> JSONResponse:
    err = cast(GitHubNotFoundError, exc)
    logger.warning("GitHub resource not found: %s", err.message)
    return _error_response(404, err.code, err.message)


async def _handle_github_rate_limit(request: Request, exc: Exception) -> JSONResponse:
    err = cast(GitHubRateLimitError, exc)
    logger.warning("GitHub rate limit exceeded. Resets at: %s", err.reset_at)
    return _error_response(429, err.code, err.message)


async def _handle_github_auth_error(request: Request, exc: Exception) -> JSONResponse:
    err = cast(GitHubAuthenticationError, exc)
    logger.error("GitHub authentication failed.")
    return _error_response(401, err.code, err.message)


async def _handle_github_api_error(request: Request, exc: Exception) -> JSONResponse:
    err = cast(GitHubAPIError, exc)
    logger.error("GitHub API error: %s", err.message)
    return _error_response(502, err.code, err.message)


async def _handle_auth_error(request: Request, exc: Exception) -> JSONResponse:
    err = cast(AuthenticationError, exc)
    logger.warning("Authentication required: %s", err.message)
    return _error_response(401, err.code, err.message)


async def _handle_oauth_error(request: Request, exc: Exception) -> JSONResponse:
    err = cast(OAuthError, exc)
    logger.warning("OAuth error: %s", err.message)
    return _error_response(400, err.code, err.message)


async def _handle_oauth_not_configured(request: Request, exc: Exception) -> JSONResponse:
    err = cast(OAuthNotConfiguredError, exc)
    logger.error("OAuth not configured.")
    return _error_response(503, err.code, err.message)


async def _handle_prinsight_error(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for any PRInsightError subclass not handled above."""
    err = cast(PRInsightError, exc)
    logger.error("Application error: %s", err.message)
    return _error_response(500, err.code, err.message)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic request validation failures."""
    err = cast(RequestValidationError, exc)
    logger.warning("Request validation error: %s", err.errors())
    return _error_response(
        422,
        "VALIDATION_ERROR",
        "Request validation failed.",
        details=err.errors(),
    )


async def _handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for any unhandled exception.

    Logs the full traceback but returns only a generic message to the client.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI application.

    Handler order matters: more specific exceptions must be registered
    before their parent classes. FastAPI matches handlers by exact type,
    so subclass handlers take priority when registered first.
    """
    # Authentication exceptions
    app.add_exception_handler(AuthenticationError, _handle_auth_error)
    app.add_exception_handler(OAuthError, _handle_oauth_error)
    app.add_exception_handler(OAuthNotConfiguredError, _handle_oauth_not_configured)

    # Specific GitHub exceptions
    app.add_exception_handler(InvalidPRURLError, _handle_invalid_pr_url)
    app.add_exception_handler(GitHubNotFoundError, _handle_github_not_found)
    app.add_exception_handler(GitHubRateLimitError, _handle_github_rate_limit)
    app.add_exception_handler(GitHubAuthenticationError, _handle_github_auth_error)
    app.add_exception_handler(GitHubAPIError, _handle_github_api_error)

    # Generic PRInsight errors (catch-all for typed exceptions)
    app.add_exception_handler(PRInsightError, _handle_prinsight_error)

    # Pydantic validation errors
    app.add_exception_handler(RequestValidationError, _handle_validation_error)

    # Unhandled exceptions (last resort)
    app.add_exception_handler(Exception, _handle_unhandled_exception)
