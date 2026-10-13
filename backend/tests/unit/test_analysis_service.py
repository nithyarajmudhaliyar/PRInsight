"""
Unit tests for AnalysisService with request-scoped credentials.

Tests cover:
    - User token propagates to all GitHub API calls during analysis
    - Default (None) token propagates when no user token is provided
    - Authentication failure terminates immediately without backend fallback
    - Concurrent analyses with different user tokens remain isolated
"""

import asyncio
import hashlib
import logging
from unittest.mock import AsyncMock

import pytest

from app.cache.memory import TTLCache
from app.clients.github_client import GitHubClient
from app.core.config import Settings
from app.exceptions.github import GitHubAuthenticationError
from app.services.analysis_service import AnalysisService, build_analysis_cache_key


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


class TestAnalysisServiceCacheIsolation:
    """
    Tests verifying cache isolation by authorization context.

    Covers:
        - Cache key structure for anonymous and authenticated requests
        - Same PR URL and same token: cache reuse (cache hit)
        - Same PR URL and different tokens: cache isolation (cache miss)
        - Same PR URL with anonymous vs authenticated: cache isolation
        - User token identical to backend GITHUB_TOKEN remains isolated
        - Raw tokens never appear in cache keys or logs
    """

    def test_build_cache_key_anonymous(self):
        url = "https://github.com/owner/repo/pull/1"
        key_none = build_analysis_cache_key(url, access_token=None)
        key_empty = build_analysis_cache_key(url, access_token="")
        key_spaces = build_analysis_cache_key(url, access_token="   ")

        assert key_none == f"anon:{url}"
        assert key_empty == f"anon:{url}"
        assert key_spaces == f"anon:{url}"
        assert key_none.startswith("anon:")

    def test_build_cache_key_authenticated(self):
        url = "https://github.com/owner/repo/pull/42"
        token = "gho_my_super_secret_token_123"
        expected_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        key = build_analysis_cache_key(url, access_token=token)

        assert key == f"auth:{expected_hash}:{url}"
        assert key.startswith("auth:")
        assert token not in key

    def test_build_cache_key_normalizes_url(self):
        url_variations = [
            "https://github.com/Owner/Repo/pull/10/",
            "  https://github.com/owner/repo/pull/10  ",
            "https://GITHUB.com/owner/repo/pull/10",
        ]
        anon_keys = [build_analysis_cache_key(u, access_token=None) for u in url_variations]
        assert len(set(anon_keys)) == 1
        assert anon_keys[0] == "anon:https://github.com/owner/repo/pull/10"

        auth_keys = [build_analysis_cache_key(u, access_token="token_xyz") for u in url_variations]
        assert len(set(auth_keys)) == 1
        token_hash = hashlib.sha256(b"token_xyz").hexdigest()
        assert auth_keys[0] == f"auth:{token_hash}:https://github.com/owner/repo/pull/10"

    @pytest.mark.asyncio
    async def test_same_pr_url_same_token_reuses_cache(self, service_settings, mock_cache):
        mock_github = AsyncMock(spec=GitHubClient)
        mock_github.get_pull_request.return_value = {
            "title": "Fix bug",
            "user": {"login": "alice"},
            "html_url": "https://github.com/owner/repo/pull/1",
        }
        mock_github.get_pull_request_files.return_value = []
        mock_github.get_open_pull_requests.return_value = []

        service = AnalysisService(
            github_client=mock_github,
            cache=mock_cache,
            settings=service_settings,
        )

        user_token = "gho_user_token_abc"
        url = "https://github.com/owner/repo/pull/1"

        # First call: cache miss
        res1 = await service.analyze(url, access_token=user_token)
        assert res1.data.metadata.cache_hit is False
        assert mock_github.get_pull_request.await_count == 1

        # Second call: cache hit (reused)
        res2 = await service.analyze(url, access_token=user_token)
        assert res2.data.metadata.cache_hit is True
        assert mock_github.get_pull_request.await_count == 1  # No additional GitHub call

    @pytest.mark.asyncio
    async def test_same_pr_url_different_tokens_cache_isolated(self, service_settings, mock_cache):
        mock_github = AsyncMock(spec=GitHubClient)
        mock_github.get_pull_request.return_value = {
            "title": "Fix bug",
            "user": {"login": "alice"},
            "html_url": "https://github.com/owner/repo/pull/1",
        }
        mock_github.get_pull_request_files.return_value = []
        mock_github.get_open_pull_requests.return_value = []

        service = AnalysisService(
            github_client=mock_github,
            cache=mock_cache,
            settings=service_settings,
        )

        url = "https://github.com/owner/repo/pull/1"

        # Request with User 1 token
        res_user1 = await service.analyze(url, access_token="token_user_1")
        assert res_user1.data.metadata.cache_hit is False
        assert mock_github.get_pull_request.await_count == 1

        # Request with User 2 token for the same PR URL -> MUST be a cache miss
        res_user2 = await service.analyze(url, access_token="token_user_2")
        assert res_user2.data.metadata.cache_hit is False
        assert mock_github.get_pull_request.await_count == 2

        # Subsequent request with User 1 token reuses User 1 cache
        res_user1_cached = await service.analyze(url, access_token="token_user_1")
        assert res_user1_cached.data.metadata.cache_hit is True
        assert mock_github.get_pull_request.await_count == 2

        # Subsequent request with User 2 token reuses User 2 cache
        res_user2_cached = await service.analyze(url, access_token="token_user_2")
        assert res_user2_cached.data.metadata.cache_hit is True
        assert mock_github.get_pull_request.await_count == 2

    @pytest.mark.asyncio
    async def test_anonymous_vs_authenticated_cache_isolated(self, service_settings, mock_cache):
        mock_github = AsyncMock(spec=GitHubClient)
        mock_github.get_pull_request.return_value = {
            "title": "Fix bug",
            "user": {"login": "alice"},
            "html_url": "https://github.com/owner/repo/pull/1",
        }
        mock_github.get_pull_request_files.return_value = []
        mock_github.get_open_pull_requests.return_value = []

        service = AnalysisService(
            github_client=mock_github,
            cache=mock_cache,
            settings=service_settings,
        )

        url = "https://github.com/owner/repo/pull/1"

        # Anonymous request
        res_anon = await service.analyze(url, access_token=None)
        assert res_anon.data.metadata.cache_hit is False
        assert mock_github.get_pull_request.await_count == 1

        # Authenticated request for the same PR URL -> MUST be a cache miss
        res_auth = await service.analyze(url, access_token="gho_auth_user_tok")
        assert res_auth.data.metadata.cache_hit is False
        assert mock_github.get_pull_request.await_count == 2

        # Subsequent anonymous request reuses anonymous cache
        res_anon_cached = await service.analyze(url, access_token=None)
        assert res_anon_cached.data.metadata.cache_hit is True
        assert mock_github.get_pull_request.await_count == 2

        # Subsequent authenticated request reuses authenticated cache
        res_auth_cached = await service.analyze(url, access_token="gho_auth_user_tok")
        assert res_auth_cached.data.metadata.cache_hit is True
        assert mock_github.get_pull_request.await_count == 2

    @pytest.mark.asyncio
    async def test_token_identical_to_backend_token_remains_isolated_from_anon(self, service_settings, mock_cache):
        mock_github = AsyncMock(spec=GitHubClient)
        mock_github.get_pull_request.return_value = {
            "title": "Fix bug",
            "user": {"login": "alice"},
            "html_url": "https://github.com/owner/repo/pull/1",
        }
        mock_github.get_pull_request_files.return_value = []
        mock_github.get_open_pull_requests.return_value = []

        service = AnalysisService(
            github_client=mock_github,
            cache=mock_cache,
            settings=service_settings,
        )

        url = "https://github.com/owner/repo/pull/1"

        # Anonymous request (uses backend GITHUB_TOKEN under the hood)
        res_anon = await service.analyze(url, access_token=None)
        assert res_anon.data.metadata.cache_hit is False
        assert mock_github.get_pull_request.await_count == 1

        # Authenticated request providing the exact same token value as service_settings.GITHUB_TOKEN
        # MUST remain isolated in the 'auth' namespace
        res_auth = await service.analyze(url, access_token=service_settings.GITHUB_TOKEN)
        assert res_auth.data.metadata.cache_hit is False
        assert mock_github.get_pull_request.await_count == 2

    @pytest.mark.asyncio
    async def test_raw_tokens_never_in_cache_keys_or_logs(self, service_settings, mock_cache, caplog):
        mock_github = AsyncMock(spec=GitHubClient)
        mock_github.get_pull_request.return_value = {
            "title": "Fix bug",
            "user": {"login": "alice"},
            "html_url": "https://github.com/owner/repo/pull/1",
        }
        mock_github.get_pull_request_files.return_value = []
        mock_github.get_open_pull_requests.return_value = []

        service = AnalysisService(
            github_client=mock_github,
            cache=mock_cache,
            settings=service_settings,
        )

        secret_user_token = "gho_super_secret_analysis_token_99999"
        url = "https://github.com/owner/repo/pull/1"

        with caplog.at_level(logging.DEBUG):
            # Run analysis (cache miss -> stores in cache)
            await service.analyze(url, access_token=secret_user_token)
            # Run analysis again (cache hit -> reads from cache)
            await service.analyze(url, access_token=secret_user_token)

        # Verify raw token is not in any cache key
        for stored_key in mock_cache._store.keys():
            assert secret_user_token not in stored_key
            assert stored_key.startswith("auth:")

        # Verify raw token never appears in any logs
        assert secret_user_token not in caplog.text
        assert "Authorization" not in caplog.text

