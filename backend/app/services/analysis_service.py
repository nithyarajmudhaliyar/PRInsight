"""
Analysis workflow orchestrator.

Coordinates the full analysis lifecycle:
    1. Cache check
    2. URL parsing
    3. GitHub API calls (with bounded concurrency)
    4. Conflict detection
    5. Response assembly
    6. Cache storage

This service knows about the client interface and the engine interface
but has no knowledge of HTTP, frameworks, or response codes.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.cache.memory import TTLCache
from app.clients.github_client import GitHubClient
from app.core.config import Settings
from app.schemas.responses import (
    AnalysisData,
    AnalysisMetadata,
    AnalysisResult,
    AnalyzeResponse,
    ConflictDetail,
    PullRequestInfo,
    RepositoryInfo,
)
from app.services.conflict_engine import detect_conflicts
from app.utils.url_parser import normalize_pr_url, parse_pr_url

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Orchestrates Pull Request conflict analysis.

    All dependencies are injected via the constructor, making the
    service fully testable with mocked clients and cache.
    """

    def __init__(
        self,
        github_client: GitHubClient,
        cache: TTLCache,
        settings: Settings,
    ) -> None:
        self._github = github_client
        self._cache = cache
        self._settings = settings

    async def analyze(self, pr_url: str) -> AnalyzeResponse:
        """
        Run the full analysis workflow for a Pull Request URL.

        Args:
            pr_url: Full GitHub Pull Request URL.

        Returns:
            AnalyzeResponse with conflict data and metadata.
        """
        start_time = time.monotonic()

        # ── Step 0: Check cache ──────────────────────────────────────────
        cache_key = normalize_pr_url(pr_url)
        cached_result = await self._cache.get(cache_key)

        if cached_result is not None:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.info("Cache hit for %s (%dms)", cache_key, elapsed_ms)
            # Update metadata to reflect this is a cache hit with fresh timing.
            cached_result.data.metadata.cache_hit = True
            cached_result.data.metadata.analysis_duration_ms = elapsed_ms
            return cached_result

        # ── Step 1: Parse URL ────────────────────────────────────────────
        components = parse_pr_url(pr_url)
        logger.info(
            "Analyzing PR #%d in %s/%s",
            components.number,
            components.owner,
            components.repo,
        )

        # ── Step 2: Fetch target PR details ──────────────────────────────
        pr_data = await self._github.get_pull_request(
            components.owner, components.repo, components.number
        )

        # ── Step 3: Fetch target PR changed files ────────────────────────
        target_files_data = await self._github.get_pull_request_files(
            components.owner, components.repo, components.number
        )
        target_file_paths = {f["filename"] for f in target_files_data}

        # ── Step 4: Fetch open PRs ───────────────────────────────────────
        open_prs = await self._github.get_open_pull_requests(
            components.owner, components.repo
        )

        # Filter out the target PR itself from the open PRs list.
        open_prs = [pr for pr in open_prs if pr["number"] != components.number]

        total_open_prs = len(open_prs)
        logger.info(
            "Found %d other open PRs in %s/%s",
            total_open_prs,
            components.owner,
            components.repo,
        )

        # ── Step 5: Fetch files for each open PR (bounded concurrency) ──
        semaphore = asyncio.Semaphore(self._settings.MAX_CONCURRENT_REQUESTS)

        async def fetch_pr_files(pr: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                files = await self._github.get_pull_request_files(
                    components.owner, components.repo, pr["number"]
                )
                return {
                    "number": pr["number"],
                    "title": pr.get("title", ""),
                    "author": pr.get("user", {}).get("login", "unknown"),
                    "url": pr.get("html_url", ""),
                    "files": {f["filename"] for f in files},
                }

        other_prs_data = await asyncio.gather(
            *[fetch_pr_files(pr) for pr in open_prs]
        )

        # ── Step 6: Detect conflicts ─────────────────────────────────────
        conflict_results = detect_conflicts(target_file_paths, list(other_prs_data))

        logger.info(
            "Conflict detection complete: %d conflicts found",
            len(conflict_results),
        )

        # ── Step 7: Assemble response ────────────────────────────────────
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Determine if we hit the pagination cap.
        # GitHub returns at most per_page results. If we got exactly
        # max_prs_to_analyze, there might be more.
        prs_analyzed = len(open_prs)
        warning = None
        if prs_analyzed >= self._settings.MAX_PRS_TO_ANALYZE:
            warning = (
                f"This repository has more than {self._settings.MAX_PRS_TO_ANALYZE} "
                f"open pull requests. Only the {self._settings.MAX_PRS_TO_ANALYZE} "
                f"most recently updated were analyzed."
            )

        response = AnalyzeResponse(
            data=AnalysisData(
                repository=RepositoryInfo(
                    owner=components.owner,
                    repo=components.repo,
                ),
                pull_request=PullRequestInfo(
                    number=components.number,
                    title=pr_data.get("title", ""),
                    author=pr_data.get("user", {}).get("login", "unknown"),
                    url=pr_data.get("html_url", pr_url),
                    changed_files=sorted(target_file_paths),
                ),
                analysis=AnalysisResult(
                    total_open_prs=total_open_prs,
                    prs_analyzed=prs_analyzed,
                    conflicts_found=len(conflict_results),
                    conflicts=[
                        ConflictDetail(
                            pr_number=c.pr_number,
                            pr_title=c.pr_title,
                            pr_author=c.pr_author,
                            pr_url=c.pr_url,
                            overlapping_files=c.overlapping_files,
                            overlap_count=c.overlap_count,
                            risk_level=c.risk_level,
                        )
                        for c in conflict_results
                    ],
                ),
                metadata=AnalysisMetadata(
                    analyzed_at=datetime.now(timezone.utc),
                    analysis_duration_ms=elapsed_ms,
                    cache_hit=False,
                    total_open_prs=total_open_prs,
                    prs_analyzed=prs_analyzed,
                    warning=warning,
                ),
            )
        )

        # ── Step 8: Store in cache ───────────────────────────────────────
        await self._cache.set(cache_key, response)
        logger.info("Cached analysis result for %s (%dms)", cache_key, elapsed_ms)

        return response
