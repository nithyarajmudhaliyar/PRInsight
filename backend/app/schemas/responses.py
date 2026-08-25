"""
Outbound response models.

These models define the JSON shape returned by every endpoint.
FastAPI serializes them automatically.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import RiskLevel


# ── Sub-models (composed into the top-level response) ────────────────────────


class RepositoryInfo(BaseModel):
    """Repository identification."""

    owner: str
    repo: str


class PullRequestInfo(BaseModel):
    """Details of the target Pull Request being analyzed."""

    number: int
    title: str
    author: str
    url: str
    changed_files: list[str]


class LineRangeInfo(BaseModel):
    """A contiguous range of lines (inclusive on both ends)."""

    start: int
    end: int


class FileOverlap(BaseModel):
    """Line-level overlap detail for a single file shared by two PRs."""

    file_path: str
    has_line_overlap: bool | None = None
    target_lines: list[LineRangeInfo] = []
    other_lines: list[LineRangeInfo] = []


class ConflictDetail(BaseModel):
    """A single conflicting Pull Request and its overlapping files."""

    pr_number: int
    pr_title: str
    pr_author: str
    pr_url: str
    overlapping_files: list[str]
    overlap_count: int
    risk_level: RiskLevel
    file_details: list[FileOverlap] | None = None


class AnalysisResult(BaseModel):
    """Aggregated conflict analysis results."""

    total_open_prs: int
    prs_analyzed: int
    conflicts_found: int
    conflicts: list[ConflictDetail]


class AnalysisMetadata(BaseModel):
    """Metadata about the analysis execution."""

    analyzed_at: datetime
    analysis_duration_ms: int
    cache_hit: bool = False
    total_open_prs: int
    prs_analyzed: int
    warning: str | None = None


class AnalysisData(BaseModel):
    """Top-level data container for a successful analysis."""

    repository: RepositoryInfo
    pull_request: PullRequestInfo
    analysis: AnalysisResult
    metadata: AnalysisMetadata


# ── Top-level endpoint responses ─────────────────────────────────────────────


class AnalyzeResponse(BaseModel):
    """
    Response model for POST /api/v1/analyze.

    Wraps all analysis data in a status + data envelope for consistency.
    """

    status: str = "success"
    data: AnalysisData


class HealthResponse(BaseModel):
    """Response model for GET /api/v1/health."""

    status: str = Field(default="healthy")
    version: str
    timestamp: datetime
