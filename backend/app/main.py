"""
PRInsight FastAPI Application Factory.

This is the entry point for the application. It creates and configures
the FastAPI instance, attaches middleware, registers exception handlers,
and includes all routers.

Run with:
    uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dependencies import get_github_client
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import configure_cors
from app.exceptions.handlers import register_exception_handlers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle events.

    Startup: log startup message.
    Shutdown: close the GitHub HTTP client to release connections.
    """
    settings = get_settings()
    logger.info(
        "%s v%s starting on %s:%d",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.HOST,
        settings.PORT,
    )
    yield
    # Shutdown: close the GitHub client's HTTPX connection pool.
    github_client = get_github_client()
    await github_client.close()
    logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    """
    Application factory.

    Creates the FastAPI app, configures all cross-cutting concerns,
    and returns the fully assembled application.
    """
    settings = get_settings()

    # ── Configure logging first (before anything else logs) ──────────
    setup_logging(log_level=settings.LOG_LEVEL)

    # ── Create FastAPI instance ──────────────────────────────────────
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Analyze GitHub Pull Requests for merge conflict risks.",
        lifespan=lifespan,
    )

    # ── Attach middleware ────────────────────────────────────────────
    configure_cors(app, settings)

    # ── Register exception handlers ──────────────────────────────────
    register_exception_handlers(app)

    # ── Include routers ──────────────────────────────────────────────
    app.include_router(api_router)

    return app


# The 'app' variable is what Uvicorn discovers via `app.main:app`.
app = create_app()
