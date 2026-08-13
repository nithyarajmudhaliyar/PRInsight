"""
Analysis endpoint — the core of PRInsight.

POST /analyze accepts a GitHub PR URL and returns a conflict report.
The route handler performs ZERO business logic — it delegates entirely
to the AnalysisService.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_analysis_service
from app.schemas.requests import AnalyzeRequest
from app.schemas.responses import AnalyzeResponse
from app.services.analysis_service import AnalysisService

router = APIRouter(tags=["Analysis"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze a Pull Request for conflicts",
    description=(
        "Accepts a GitHub Pull Request URL and analyzes it for file-level "
        "conflicts against all other open Pull Requests in the same repository."
    ),
    responses={
        400: {"description": "Invalid PR URL format"},
        404: {"description": "PR or repository not found on GitHub"},
        422: {"description": "Request validation failed"},
        429: {"description": "GitHub API rate limit exceeded"},
        502: {"description": "GitHub API returned an unexpected error"},
    },
)
async def analyze_pr(
    request: AnalyzeRequest,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalyzeResponse:
    """
    Analyze a Pull Request for file-level conflicts.

    The handler validates the request body (via Pydantic), injects the
    AnalysisService (via Depends), and returns the analysis result.
    All business logic lives in the service layer.
    """
    return await service.analyze(request.pr_url)
