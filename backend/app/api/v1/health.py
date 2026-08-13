"""
Health check endpoint.

MVP: single /health endpoint returning application status.

Future: add /health/ready when external dependencies (PostgreSQL,
Redis, AI service) exist and need independent health probes.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.responses import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns application health status. Used by load balancers and uptime monitors.",
)
async def health_check() -> HealthResponse:
    """Return current application health status."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc),
    )
