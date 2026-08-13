"""
Integration tests for POST /api/v1/analyze.

Tests the full HTTP request → response flow using mocked GitHub responses.
The GitHubClient is replaced with an AsyncMock to avoid real API calls.
"""

from unittest.mock import AsyncMock, patch


class TestAnalyzeEndpoint:
    """Tests for POST /api/v1/analyze."""

    def test_missing_body_returns_422(self, test_client):
        response = test_client.post("/api/v1/analyze")
        assert response.status_code == 422
        data = response.json()
        assert data["status"] == "error"
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_empty_pr_url_returns_422(self, test_client):
        response = test_client.post("/api/v1/analyze", json={"pr_url": ""})
        assert response.status_code == 422

    def test_invalid_pr_url_returns_400(self, test_client):
        """
        A syntactically valid string that doesn't match the GitHub PR URL pattern.
        Pydantic accepts it (min_length=1), but url_parser rejects it.
        """
        from app.exceptions.validation import InvalidPRURLError
        from app.api.dependencies import get_analysis_service

        mock_service = AsyncMock()
        mock_service.analyze.side_effect = InvalidPRURLError("https://example.com/not/valid")
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://example.com/not/valid"},
            )
            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == "INVALID_PR_URL"
        finally:
            test_client.app.dependency_overrides.clear()

    def test_github_not_found_returns_404(self, test_client):
        """Simulate a GitHub 404 for a non-existent PR."""
        from app.exceptions.github import GitHubNotFoundError
        from app.api.dependencies import get_analysis_service

        mock_service = AsyncMock()
        mock_service.analyze.side_effect = GitHubNotFoundError("PR")
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/99999"},
            )
            assert response.status_code == 404
            data = response.json()
            assert data["error"]["code"] == "PR_NOT_FOUND"
        finally:
            test_client.app.dependency_overrides.clear()

    def test_github_rate_limit_returns_429(self, test_client):
        """Simulate GitHub rate limit exceeded."""
        from app.exceptions.github import GitHubRateLimitError
        from app.api.dependencies import get_analysis_service

        mock_service = AsyncMock()
        mock_service.analyze.side_effect = GitHubRateLimitError(reset_at="1720000000")
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )
            assert response.status_code == 429
            data = response.json()
            assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        finally:
            test_client.app.dependency_overrides.clear()

    def test_successful_analysis_returns_200(self, test_client):
        """Simulate a successful analysis with no conflicts."""
        from datetime import datetime, timezone
        from app.schemas.responses import (
            AnalysisData,
            AnalysisMetadata,
            AnalysisResult,
            AnalyzeResponse,
            PullRequestInfo,
            RepositoryInfo,
        )
        from app.api.dependencies import get_analysis_service

        mock_response = AnalyzeResponse(
            data=AnalysisData(
                repository=RepositoryInfo(owner="facebook", repo="react"),
                pull_request=PullRequestInfo(
                    number=12345,
                    title="Fix auth",
                    author="dev",
                    url="https://github.com/facebook/react/pull/12345",
                    changed_files=["src/auth.js"],
                ),
                analysis=AnalysisResult(
                    total_open_prs=5,
                    prs_analyzed=5,
                    conflicts_found=0,
                    conflicts=[],
                ),
                metadata=AnalysisMetadata(
                    analyzed_at=datetime.now(timezone.utc),
                    analysis_duration_ms=500,
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
                json={"pr_url": "https://github.com/facebook/react/pull/12345"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["data"]["repository"]["owner"] == "facebook"
            assert data["data"]["analysis"]["conflicts_found"] == 0
        finally:
            test_client.app.dependency_overrides.clear()

    def test_error_response_envelope_is_consistent(self, test_client):
        """Every error response must have status, error.code, error.message."""
        response = test_client.post("/api/v1/analyze")
        data = response.json()

        assert "status" in data
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
