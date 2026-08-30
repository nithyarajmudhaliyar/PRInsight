"""
Security tests — verify GITHUB_TOKEN is never exposed to clients.

These tests confirm that the server-side GitHub token is never
returned in API responses, error messages, or health check output.
"""

import pytest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_analysis_service
from app.exceptions.github import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)


class TestGitHubTokenNotLeaked:
    """Verify that GITHUB_TOKEN value never appears in API responses."""

    def _assert_no_token_in_response(self, response):
        """Check that no GitHub token pattern appears in the response body."""
        body = response.text
        # The test env token is "ghp_test_token_for_testing"
        assert "ghp_test_token_for_testing" not in body
        # Also check for common token prefixes that shouldn't appear
        assert "ghp_" not in body or "ghp_your" in body  # allow .env.example placeholder
        assert "GITHUB_TOKEN" not in body

    def test_health_endpoint_does_not_leak_token(self, test_client: TestClient):
        """GET /health should not contain the token."""
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        self._assert_no_token_in_response(response)

    def test_successful_analysis_does_not_leak_token(self, test_client: TestClient):
        """A successful 200 response should not contain the token."""
        from datetime import datetime, timezone
        from app.schemas.responses import (
            AnalysisData, AnalysisMetadata, AnalysisResult,
            AnalyzeResponse, PullRequestInfo, RepositoryInfo,
        )

        mock_response = AnalyzeResponse(
            data=AnalysisData(
                repository=RepositoryInfo(owner="owner", repo="repo"),
                pull_request=PullRequestInfo(
                    number=1, title="Test", author="dev",
                    url="https://github.com/owner/repo/pull/1",
                    changed_files=["file.py"],
                ),
                analysis=AnalysisResult(
                    total_open_prs=0, prs_analyzed=0,
                    conflicts_found=0, conflicts=[],
                ),
                metadata=AnalysisMetadata(
                    analyzed_at=datetime.now(timezone.utc),
                    analysis_duration_ms=100, cache_hit=False,
                    total_open_prs=0, prs_analyzed=0,
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
            self._assert_no_token_in_response(response)
        finally:
            test_client.app.dependency_overrides.clear()

    def test_auth_error_does_not_leak_token(self, test_client: TestClient):
        """A 401 GitHub auth error should not reveal the token or its env var name."""
        mock_service = AsyncMock()
        mock_service.analyze.side_effect = GitHubAuthenticationError()
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )
            assert response.status_code == 401
            self._assert_no_token_in_response(response)
        finally:
            test_client.app.dependency_overrides.clear()

    def test_not_found_error_does_not_leak_token(self, test_client: TestClient):
        """A 404 error should not reveal the token."""
        mock_service = AsyncMock()
        mock_service.analyze.side_effect = GitHubNotFoundError("PR")
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )
            assert response.status_code == 404
            self._assert_no_token_in_response(response)
        finally:
            test_client.app.dependency_overrides.clear()

    def test_rate_limit_error_does_not_leak_token(self, test_client: TestClient):
        """A 429 GitHub rate limit error should not reveal the token."""
        mock_service = AsyncMock()
        mock_service.analyze.side_effect = GitHubRateLimitError()
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )
            assert response.status_code == 429
            self._assert_no_token_in_response(response)
        finally:
            test_client.app.dependency_overrides.clear()

    def test_server_error_does_not_leak_token(self, test_client: TestClient):
        """A 502 GitHub API error should not reveal the token."""
        mock_service = AsyncMock()
        mock_service.analyze.side_effect = GitHubAPIError(status_code=500, detail="Internal")
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/analyze",
                json={"pr_url": "https://github.com/owner/repo/pull/1"},
            )
            assert response.status_code == 502
            self._assert_no_token_in_response(response)
        finally:
            test_client.app.dependency_overrides.clear()

    def test_unhandled_error_does_not_leak_token(self, test_client: TestClient):
        """An unhandled exception should return a generic message without the token."""
        mock_service = AsyncMock()
        mock_service.analyze.side_effect = RuntimeError("Something unexpected")
        test_client.app.dependency_overrides[get_analysis_service] = lambda: mock_service

        try:
            # Use raise_server_exceptions=False so the 500 response
            # is returned instead of re-raising through TestClient.
            with TestClient(test_client.app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/api/v1/analyze",
                    json={"pr_url": "https://github.com/owner/repo/pull/1"},
                )
                assert response.status_code == 500
                self._assert_no_token_in_response(response)
        finally:
            test_client.app.dependency_overrides.clear()

    def test_validation_error_does_not_leak_token(self, test_client: TestClient):
        """A 422 validation error should not reveal the token."""
        response = test_client.post("/api/v1/analyze", json={"pr_url": ""})
        assert response.status_code == 422
        self._assert_no_token_in_response(response)
