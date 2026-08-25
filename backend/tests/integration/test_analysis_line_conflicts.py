"""
Integration tests for line-level conflict detection in POST /api/v1/analyze.

Tests verify that the full HTTP request → response flow correctly includes
file_details with line-level overlap information in the ConflictDetail.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.api.dependencies import get_analysis_service
from app.schemas.responses import (
    AnalysisData,
    AnalysisMetadata,
    AnalysisResult,
    AnalyzeResponse,
    ConflictDetail,
    FileOverlap,
    LineRangeInfo,
    PullRequestInfo,
    RepositoryInfo,
)


class TestLineConflictResponse:
    """Tests for line-level conflict data in the analysis response."""

    def test_response_includes_file_details_with_line_overlap(self, test_client):
        """Verify file_details appears in the response with line overlap data."""
        mock_response = AnalyzeResponse(
            data=AnalysisData(
                repository=RepositoryInfo(owner="owner", repo="repo"),
                pull_request=PullRequestInfo(
                    number=1,
                    title="Target PR",
                    author="dev",
                    url="https://github.com/owner/repo/pull/1",
                    changed_files=["src/auth.py"],
                ),
                analysis=AnalysisResult(
                    total_open_prs=2,
                    prs_analyzed=2,
                    conflicts_found=1,
                    conflicts=[
                        ConflictDetail(
                            pr_number=2,
                            pr_title="Other PR",
                            pr_author="other-dev",
                            pr_url="https://github.com/owner/repo/pull/2",
                            overlapping_files=["src/auth.py"],
                            overlap_count=1,
                            risk_level="low",
                            file_details=[
                                FileOverlap(
                                    file_path="src/auth.py",
                                    has_line_overlap=True,
                                    target_lines=[LineRangeInfo(start=10, end=20)],
                                    other_lines=[LineRangeInfo(start=15, end=25)],
                                )
                            ],
                        )
                    ],
                ),
                metadata=AnalysisMetadata(
                    analyzed_at=datetime.now(timezone.utc),
                    analysis_duration_ms=100,
                    cache_hit=False,
                    total_open_prs=2,
                    prs_analyzed=2,
                ),
            )
        )

        mock_service = AsyncMock()
        mock_service.analyze.return_value = mock_response
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )
            assert response.status_code == 200
            data = response.json()

            conflict = data["data"]["analysis"]["conflicts"][0]
            assert "file_details" in conflict
            assert len(conflict["file_details"]) == 1

            file_detail = conflict["file_details"][0]
            assert file_detail["file_path"] == "src/auth.py"
            assert file_detail["has_line_overlap"] is True
            assert file_detail["target_lines"] == [{"start": 10, "end": 20}]
            assert file_detail["other_lines"] == [{"start": 15, "end": 25}]
        finally:
            test_client.app.dependency_overrides.clear()

    def test_response_includes_file_details_fallback(self, test_client):
        """Verify file_details shows has_line_overlap=None for fallback."""
        mock_response = AnalyzeResponse(
            data=AnalysisData(
                repository=RepositoryInfo(owner="owner", repo="repo"),
                pull_request=PullRequestInfo(
                    number=1,
                    title="Target PR",
                    author="dev",
                    url="https://github.com/owner/repo/pull/1",
                    changed_files=["binary_file.png"],
                ),
                analysis=AnalysisResult(
                    total_open_prs=1,
                    prs_analyzed=1,
                    conflicts_found=1,
                    conflicts=[
                        ConflictDetail(
                            pr_number=2,
                            pr_title="Other PR",
                            pr_author="other-dev",
                            pr_url="https://github.com/owner/repo/pull/2",
                            overlapping_files=["binary_file.png"],
                            overlap_count=1,
                            risk_level="low",
                            file_details=[
                                FileOverlap(
                                    file_path="binary_file.png",
                                    has_line_overlap=None,
                                    target_lines=[],
                                    other_lines=[],
                                )
                            ],
                        )
                    ],
                ),
                metadata=AnalysisMetadata(
                    analyzed_at=datetime.now(timezone.utc),
                    analysis_duration_ms=50,
                    cache_hit=False,
                    total_open_prs=1,
                    prs_analyzed=1,
                ),
            )
        )

        mock_service = AsyncMock()
        mock_service.analyze.return_value = mock_response
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )
            assert response.status_code == 200
            data = response.json()

            conflict = data["data"]["analysis"]["conflicts"][0]
            file_detail = conflict["file_details"][0]
            assert file_detail["has_line_overlap"] is None
            assert file_detail["target_lines"] == []
            assert file_detail["other_lines"] == []
        finally:
            test_client.app.dependency_overrides.clear()

    def test_response_without_conflicts_has_no_file_details(self, test_client):
        """When there are no conflicts, the conflicts list is empty."""
        mock_response = AnalyzeResponse(
            data=AnalysisData(
                repository=RepositoryInfo(owner="owner", repo="repo"),
                pull_request=PullRequestInfo(
                    number=1,
                    title="Target PR",
                    author="dev",
                    url="https://github.com/owner/repo/pull/1",
                    changed_files=["unique_file.py"],
                ),
                analysis=AnalysisResult(
                    total_open_prs=5,
                    prs_analyzed=5,
                    conflicts_found=0,
                    conflicts=[],
                ),
                metadata=AnalysisMetadata(
                    analyzed_at=datetime.now(timezone.utc),
                    analysis_duration_ms=80,
                    cache_hit=False,
                    total_open_prs=5,
                    prs_analyzed=5,
                ),
            )
        )

        mock_service = AsyncMock()
        mock_service.analyze.return_value = mock_response
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["analysis"]["conflicts"] == []
        finally:
            test_client.app.dependency_overrides.clear()
