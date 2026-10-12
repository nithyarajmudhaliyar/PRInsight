"""
Unit tests for AnalysisService with request-scoped credentials.

Tests cover:
    - User token propagates to all GitHub API calls during analysis
    - Default (None) token propagates when no user token is provided
    - Authentication failure terminates immediately without backend fallback
    - Concurrent analyses with different user tokens remain isolated
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.cache.memory import TTLCache
from app.clients.github_client import GitHubClient
from app.core.config import Settings
from app.exceptions.github import GitHubAuthenticationError
from app.services.analysis_service import AnalysisService


@pytest.fixture
def service_settings() -> Settings:
    return Settings(
        GITHUB_TOKEN="backend_token_123",
        MAX_CONCURRENT_REQUESTS=5,
        MAX_PRS_TO_ANALYZE=10,
        CACHE_TTL_SECONDS=3600,
    )


@pytest.fixture
def mock_cache() -> TTLCache:
    return TTLCache(ttl=3600, max_entries=100)


class TestAnalysisServiceCredentialPropagation:
    """Tests verifying credential propagation across the entire analysis workflow."""

    @pytest.mark.asyncio
    async def test_analysis_propagates_user_token_to_all_github_calls(self, service_settings, mock_cache):
        mock_github = AsyncMock(spec=GitHubClient)
        mock_github.get_pull_request.return_value = {
            "title": "Fix bug",
            "user": {"login": "alice"},
            "html_url": "https://github.com/owner/repo/pull/10",
        }
        mock_github.get_pull_request_files.side_effect = [
            # Target PR files
            [{"filename": "app/main.py", "patch": "@@ -1,3 +1,3 @@"}],
            # Open PR #11 files
            [{"filename": "app/main.py", "patch": "@@ -1,3 +1,3 @@"}],
        ]
        mock_github.get_open_pull_requests.return_value = [
            {
                "number": 11,
                "title": "Other PR",
                "user": {"login": "bob"},
                "html_url": "https://github.com/owner/repo/pull/11",
            }
        ]

        service = AnalysisService(
            github_client=mock_github,
            cache=mock_cache,
            settings=service_settings,
        )

        user_token = "gho_user_alice_token_xyz"
        response = await service.analyze(
            "https://github.com/owner/repo/pull/10",
            access_token=user_token,
        )

        assert response.data.pull_request.number == 10
        assert response.data.analysis.conflicts_found == 1

        # Verify get_pull_request used the token
        mock_github.get_pull_request.assert_awaited_once_with(
            "owner", "repo", 10, access_token=user_token
        )

        # Verify get_open_pull_requests used the token
        mock_github.get_open_pull_requests.assert_awaited_once_with(
            "owner", "repo", access_token=user_token
        )

        # Verify get_pull_request_files was called with the token for both target and other PR
        assert mock_github.get_pull_request_files.await_count == 2
        for call in mock_github.get_pull_request_files.await_args_list:
            assert call.kwargs.get("access_token") == user_token

    @pytest.mark.asyncio
    async def test_analysis_without_token_passes_none(self, service_settings, mock_cache):
        mock_github = AsyncMock(spec=GitHubClient)
        mock_github.get_pull_request.return_value = {
            "title": "Anonymous Analysis",
            "user": {"login": "charlie"},
            "html_url": "https://github.com/owner/repo/pull/5",
        }
        mock_github.get_pull_request_files.return_value = []
        mock_github.get_open_pull_requests.return_value = []

        service = AnalysisService(
            github_client=mock_github,
            cache=mock_cache,
            settings=service_settings,
        )

        await service.analyze("https://github.com/owner/repo/pull/5")

        mock_github.get_pull_request.assert_awaited_once_with(
            "owner", "repo", 5, access_token=None
        )
        mock_github.get_open_pull_requests.assert_awaited_once_with(
            "owner", "repo", access_token=None
        )
        assert mock_github.get_pull_request_files.await_args.kwargs.get("access_token") is None

    @pytest.mark.asyncio
    async def test_rejected_token_aborts_without_fallback(self, service_settings, mock_cache):
        mock_github = AsyncMock(spec=GitHubClient)
        mock_github.get_pull_request.side_effect = GitHubAuthenticationError()

        service = AnalysisService(
            github_client=mock_github,
            cache=mock_cache,
            settings=service_settings,
        )

        with pytest.raises(GitHubAuthenticationError):
            await service.analyze(
                "https://github.com/owner/repo/pull/1",
                access_token="gho_bad_token",
            )

        # Must not call any other endpoints or retry
        mock_github.get_pull_request.assert_awaited_once_with(
            "owner", "repo", 1, access_token="gho_bad_token"
        )
        mock_github.get_open_pull_requests.assert_not_awaited()
        mock_github.get_pull_request_files.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_concurrent_analyses_maintain_token_isolation(self, service_settings):
        # Use separate cache per test to avoid cross-contamination
        cache = TTLCache(ttl=3600, max_entries=100)
        mock_github = AsyncMock(spec=GitHubClient)

        def mock_get_pr(owner, repo, number, access_token=None):
            return {
                "title": f"PR #{number}",
                "user": {"login": f"user_{number}"},
                "html_url": f"https://github.com/{owner}/{repo}/pull/{number}",
            }

        mock_github.get_pull_request.side_effect = mock_get_pr
        mock_github.get_pull_request_files.return_value = []
        mock_github.get_open_pull_requests.return_value = []

        service = AnalysisService(
            github_client=mock_github,
            cache=cache,
            settings=service_settings,
        )

        # Concurrently run analysis with two different user tokens
        task_1 = service.analyze(
            "https://github.com/owner/repo/pull/1",
            access_token="token_user_alpha",
        )
        task_2 = service.analyze(
            "https://github.com/owner/repo/pull/2",
            access_token="token_user_beta",
        )

        await asyncio.gather(task_1, task_2)

        # Verify call arguments
        calls = {
            call.args[2]: call.kwargs.get("access_token")
            for call in mock_github.get_pull_request.await_args_list
        }
        assert calls[1] == "token_user_alpha"
        assert calls[2] == "token_user_beta"
