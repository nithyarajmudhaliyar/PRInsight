"""
Central router that includes all versioned sub-routers.

All endpoints are mounted under /api/v1/. Future versions (v2/)
will be added as additional includes here.
"""

from fastapi import APIRouter

from app.api.v1.analysis import router as analysis_router
from app.api.v1.health import router as health_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(analysis_router)
