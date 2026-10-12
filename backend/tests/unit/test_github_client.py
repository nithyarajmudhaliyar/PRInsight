"""
Unit tests for GitHubClient request-scoped credentials.

Tests cover:
    - User token used in Authorization headers when provided
    - Backend GITHUB_TOKEN used as fallback when no user token is provided
    - Shared HTTP client headers are never mutated
    - Concurrent requests with different tokens remain strictly isolated
    - Supplied token propagates to all GitHub API methods
    - Token is preserved across retries
    - 401/403 errors never trigger fallback to backend token
    - Tokens are never exposed in logs
"""

import asyncio
import logging
from unittest.mock import patch

import httpx
import pytest

from app.clients.github_client import GitHubClient
from app.core.config import Settings
from app.exceptions.github import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)


@pytest.fixture
def client_settings() -> Settings:
    return Settings(
        GITHUB_TOKEN="backend_secret_token_12345",
        GITHUB_API_BASE_URL="https://api.github.com",
        GITHUB_API_TIMEOUT=10,
        GITHUB_MAX_RETRIES=2,
    )


class TestGitHubClientCredentials:
    """Tests verifying credential selection, propagation, and isolation in GitHubClient."""

    @pytest.mark.asyncio
    async def test_user_token_used_in_authorization_header(self, client_settings):
        captured_auth = []

        def handler(request: httpx.Request):
            captured_auth.append(request.headers.get("authorization"))
            return httpx.Response(200, json={"id": 1, "number": 42})

        client = GitHubClient(client_settings)
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=client_settings.GITHUB_API_BASE_URL,
        )

        user_token = "gho_user_specific_access_token_abc"
        res = await client.get_pull_request("owner", "repo", 42, access_token=user_token)

        assert res["number"] == 42
        assert len(captured_auth) == 1
        assert captured_auth[0] == f"Bearer {user_token}"
        await client.close()

    @pytest.mark.asyncio
    async def test_backend_token_used_when_no_user_token(self, client_settings):
        captured_auth = []

        def handler(request: httpx.Request):
            captured_auth.append(request.headers.get("authorization"))
            return httpx.Response(200, json={"id": 1, "number": 42})

        client = GitHubClient(client_settings)
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=client_settings.GITHUB_API_BASE_URL,
        )

        res = await client.get_pull_request("owner", "repo", 42, access_token=None)

        assert res["number"] == 42
        assert len(captured_auth) == 1
        assert captured_auth[0] == f"Bearer {client_settings.GITHUB_TOKEN}"
        await client.close()

    @pytest.mark.asyncio
    async def test_no_auth_header_when_both_tokens_empty(self):
        settings_no_token = Settings(
            GITHUB_TOKEN="",
            GITHUB_API_BASE_URL="https://api.github.com",
        )
        captured_auth = []

        def handler(request: httpx.Request):
            captured_auth.append(request.headers.get("authorization"))
            return httpx.Response(200, json={"id": 1})

        client = GitHubClient(settings_no_token)
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=settings_no_token.GITHUB_API_BASE_URL,
        )

        await client.get_pull_request("owner", "repo", 1, access_token=None)

        assert len(captured_auth) == 1
        assert captured_auth[0] is None
        await client.close()

    @pytest.mark.asyncio
    async def test_client_headers_not_mutated_when_switching_tokens(self, client_settings):
        client = GitHubClient(client_settings)

        # Ensure "Authorization" is never on the persistent client headers
        assert "authorization" not in client._client.headers

        def handler(request: httpx.Request):
            return httpx.Response(200, json=[])

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=client_settings.GITHUB_API_BASE_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "PRInsight/0.1.0",
            },
        )

        # Make request with user token A
        await client.get_pull_request("owner", "repo", 1, access_token="token_A")
        assert "authorization" not in client._client.headers

        # Make request with user token B
        await client.get_pull_request("owner", "repo", 2, access_token="token_B")
        assert "authorization" not in client._client.headers

        # Make request with default token (None)
        await client.get_pull_request("owner", "repo", 3, access_token=None)
        assert "authorization" not in client._client.headers

        await client.close()

    @pytest.mark.asyncio
    async def test_concurrent_requests_remain_isolated(self, client_settings):
        """Simulate concurrent API requests using different tokens and verify no leakage."""
        client = GitHubClient(client_settings)
        received_requests = []

        def handler(request: httpx.Request):
            auth = request.headers.get("authorization")
            path = str(request.url.path)
            received_requests.append((path, auth))
            return httpx.Response(200, json={"path": path})

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=client_settings.GITHUB_API_BASE_URL,
        )

        async def worker(index: int, token: str | None):
            await asyncio.sleep(0.01 * (index % 3))  # Jitter to interleave
            await client.get_pull_request("owner", "repo", index, access_token=token)

        tasks = [
            worker(1, "token_user_1"),
            worker(2, "token_user_2"),
            worker(3, None),  # Uses backend token
            worker(4, "token_user_4"),
            worker(5, None),  # Uses backend token
            worker(6, "token_user_6"),
        ]
        await asyncio.gather(*tasks)

        assert len(received_requests) == 6
        for path, auth in received_requests:
            if path.endswith("/1"):
                assert auth == "Bearer token_user_1"
            elif path.endswith("/2"):
                assert auth == "Bearer token_user_2"
            elif path.endswith("/3"):
                assert auth == f"Bearer {client_settings.GITHUB_TOKEN}"
            elif path.endswith("/4"):
                assert auth == "Bearer token_user_4"
            elif path.endswith("/5"):
                assert auth == f"Bearer {client_settings.GITHUB_TOKEN}"
            elif path.endswith("/6"):
                assert auth == "Bearer token_user_6"

        await client.close()

    @pytest.mark.asyncio
    async def test_credential_propagates_to_all_client_methods(self, client_settings):
        user_token = "gho_propagation_test_token"
        captured = []

        def handler(request: httpx.Request):
            captured.append((request.url.path, request.headers.get("authorization")))
            return httpx.Response(200, json=[])

        client = GitHubClient(client_settings)
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=client_settings.GITHUB_API_BASE_URL,
        )

        await client.get_pull_request("org", "repo", 10, access_token=user_token)
        await client.get_pull_request_files("org", "repo", 10, access_token=user_token)
        await client.get_open_pull_requests("org", "repo", max_prs=5, access_token=user_token)

        assert len(captured) == 3
        for _, auth in captured:
            assert auth == f"Bearer {user_token}"

        await client.close()


class TestGitHubClientRetriesAndErrors:
    """Tests verifying retry handling and strict non-fallback security."""

    @pytest.mark.asyncio
    async def test_token_preserved_across_retries(self, client_settings):
        attempts = 0
        captured_auth = []

        def handler(request: httpx.Request):
            nonlocal attempts
            attempts += 1
            captured_auth.append(request.headers.get("authorization"))
            if attempts == 1:
                return httpx.Response(500, text="Internal Server Error")
            return httpx.Response(200, json={"success": True})

        client = GitHubClient(client_settings)
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=client_settings.GITHUB_API_BASE_URL,
        )

        user_token = "gho_retry_token_999"
        with patch("asyncio.sleep", return_value=None):
            res = await client.get_pull_request("owner", "repo", 1, access_token=user_token)

        assert res["success"] is True
        assert attempts == 2
        assert captured_auth == [f"Bearer {user_token}", f"Bearer {user_token}"]
        await client.close()

    @pytest.mark.asyncio
    async def test_rejected_user_token_raises_auth_error_without_fallback(self, client_settings):
        call_count = 0
        captured_auth = []

        def handler(request: httpx.Request):
            nonlocal call_count
            call_count += 1
            captured_auth.append(request.headers.get("authorization"))
            return httpx.Response(401, json={"message": "Bad credentials"})

        client = GitHubClient(client_settings)
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=client_settings.GITHUB_API_BASE_URL,
        )

        bad_user_token = "gho_invalid_expired_token_123"
        with pytest.raises(GitHubAuthenticationError):
            await client.get_pull_request("owner", "repo", 1, access_token=bad_user_token)

        # Must NOT retry or fall back to backend token
        assert call_count == 1
        assert captured_auth == [f"Bearer {bad_user_token}"]
        await client.close()

    @pytest.mark.asyncio
    async def test_permission_denied_raises_api_error_without_fallback(self, client_settings):
        call_count = 0
        captured_auth = []

        def handler(request: httpx.Request):
            nonlocal call_count
            call_count += 1
            captured_auth.append(request.headers.get("authorization"))
            return httpx.Response(403, json={"message": "Resource not accessible by personal access token"})

        client = GitHubClient(client_settings)
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=client_settings.GITHUB_API_BASE_URL,
        )

        user_token = "gho_low_privilege_token_456"
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_pull_request("owner", "repo", 1, access_token=user_token)

        assert exc_info.value.status_code == 403
        assert call_count == 1
        assert captured_auth == [f"Bearer {user_token}"]
        await client.close()

    @pytest.mark.asyncio
    async def test_tokens_never_logged(self, client_settings, caplog):
        def handler(request: httpx.Request):
            return httpx.Response(200, json={"number": 1})

        client = GitHubClient(client_settings)
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=client_settings.GITHUB_API_BASE_URL,
        )

        secret_token = "gho_super_secret_user_token_777888"
        with caplog.at_level(logging.DEBUG):
            await client.get_pull_request("owner", "repo", 1, access_token=secret_token)

        assert secret_token not in caplog.text
        assert client_settings.GITHUB_TOKEN not in caplog.text
        assert "Authorization" not in caplog.text
        await client.close()
