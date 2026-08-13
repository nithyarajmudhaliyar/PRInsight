"""
GitHub REST API client.

Self-contained HTTPX-based client that encapsulates all communication
with the GitHub API. No base_client.py abstraction — all HTTP config
(timeouts, headers, retries) lives here.

Future migration path:
    When a second external client is introduced (e.g., ai_client.py),
    extract shared constructor concerns (AsyncClient setup, retry logic,
    default headers) into a base_client.py. The extraction is a
    straightforward refactor because all HTTP config is co-located here.
"""

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.core.constants import GITHUB_PER_PAGE
from app.exceptions.github import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)

logger = logging.getLogger(__name__)


class GitHubClient:
    """
    Async client for the GitHub REST API.

    Manages its own HTTPX AsyncClient lifecycle. Must be used as an
    async context manager or explicitly closed via close().

    Attributes:
        settings: Application settings (token, base URL, timeouts).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.GITHUB_API_BASE_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
                "User-Agent": f"{settings.APP_NAME}/{settings.APP_VERSION}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=httpx.Timeout(timeout=float(settings.GITHUB_API_TIMEOUT)),
        )

    async def close(self) -> None:
        """Close the underlying HTTPX client."""
        await self._client.aclose()

    # ── Public API methods ───────────────────────────────────────────────

    async def get_pull_request(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        """
        Fetch a single Pull Request by number.

        GET /repos/{owner}/{repo}/pulls/{number}
        """
        path = f"/repos/{owner}/{repo}/pulls/{number}"
        return await self._request("GET", path)

    async def get_pull_request_files(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        """
        Fetch the list of files changed in a Pull Request.

        GET /repos/{owner}/{repo}/pulls/{number}/files?per_page=100

        Returns up to 100 files (GitHub's maximum per page).
        For PRs with more than 100 changed files, only the first page
        is returned in the MVP.
        """
        path = f"/repos/{owner}/{repo}/pulls/{number}/files"
        return await self._request("GET", path, params={"per_page": GITHUB_PER_PAGE})

    async def get_open_pull_requests(self, owner: str, repo: str, max_prs: int | None = None) -> list[dict[str, Any]]:
        """
        Fetch open Pull Requests for a repository.

        GET /repos/{owner}/{repo}/pulls?state=open&per_page={max_prs}&sort=updated&direction=desc

        Returns at most max_prs results (default: settings.MAX_PRS_TO_ANALYZE).
        The most recently updated PRs are returned first.
        """
        per_page = max_prs or self._settings.MAX_PRS_TO_ANALYZE
        path = f"/repos/{owner}/{repo}/pulls"
        return await self._request(
            "GET",
            path,
            params={
                "state": "open",
                "per_page": per_page,
                "sort": "updated",
                "direction": "desc",
            },
        )

    # ── Internal request handling ────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute an HTTP request with retry logic for transient failures.

        Retries on:
            - 5xx server errors (GitHub infrastructure issues)
            - 429 rate limit (with exponential backoff)
            - Network timeouts

        Raises typed exceptions for non-retryable failures.
        """
        last_exception: Exception | None = None

        for attempt in range(1, self._settings.GITHUB_MAX_RETRIES + 1):
            try:
                response = await self._client.request(method, path, params=params)

                logger.info(
                    "GitHub API: %s %s — %d — attempt %d",
                    method,
                    path,
                    response.status_code,
                    attempt,
                )

                # Successful response
                if response.status_code == 200:
                    return response.json()

                # Non-retryable client errors
                if response.status_code == 404:
                    raise GitHubNotFoundError(resource=f"{path}")

                if response.status_code == 401:
                    raise GitHubAuthenticationError()

                if response.status_code == 403:
                    # Could be rate limit or abuse detection
                    remaining = response.headers.get("x-ratelimit-remaining", "")
                    if remaining == "0":
                        reset_at = response.headers.get("x-ratelimit-reset", None)
                        raise GitHubRateLimitError(reset_at=reset_at)
                    # Abuse detection — treat as rate limit
                    raise GitHubRateLimitError()

                if response.status_code == 429:
                    reset_at = response.headers.get("x-ratelimit-reset", None)
                    raise GitHubRateLimitError(reset_at=reset_at)

                # Retryable server errors (5xx)
                if response.status_code >= 500:
                    last_exception = GitHubAPIError(
                        status_code=response.status_code,
                        detail=response.text[:200],
                    )
                    if attempt < self._settings.GITHUB_MAX_RETRIES:
                        wait = 2**attempt  # Exponential backoff: 2s, 4s
                        logger.warning(
                            "GitHub API returned %d, retrying in %ds (attempt %d/%d)",
                            response.status_code,
                            wait,
                            attempt,
                            self._settings.GITHUB_MAX_RETRIES,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise last_exception

                # Unexpected status code — don't retry
                raise GitHubAPIError(
                    status_code=response.status_code,
                    detail=response.text[:200],
                )

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exception = exc
                if attempt < self._settings.GITHUB_MAX_RETRIES:
                    wait = 2**attempt
                    logger.warning(
                        "GitHub API request failed (%s), retrying in %ds (attempt %d/%d)",
                        type(exc).__name__,
                        wait,
                        attempt,
                        self._settings.GITHUB_MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue

                logger.error("GitHub API request failed after %d attempts: %s", attempt, exc)
                raise GitHubAPIError(
                    status_code=0,
                    detail=f"Connection failed after {attempt} attempts: {exc}",
                ) from exc

        # Should not reach here, but safety net.
        if last_exception:
            raise last_exception  # pragma: no cover
        raise GitHubAPIError(status_code=0, detail="Request failed with no response.")  # pragma: no cover
