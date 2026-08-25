"""
Conflict detection engine.

Pure-logic module with zero I/O dependencies. Receives file data,
computes set intersections, and assigns risk levels.

This is the most critical business logic in the application and is
trivially unit-testable because it has no side effects.

Supports two modes:
    1. File-level detection (original): detect_conflicts()
    2. Line-level detection (enhanced): detect_conflicts_with_lines()
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.constants import (
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
)
from app.utils.diff_parser import LineRange, parse_patch, ranges_overlap

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileOverlapDetail:
    """
    Line-level overlap information for a single file shared by two PRs.

    Attributes:
        file_path: The file that both PRs modify.
        has_line_overlap: True if changed lines overlap, False if they don't,
                          None if line-level data was unavailable (fallback).
        target_lines: Line ranges changed in the target PR.
        other_lines: Line ranges changed in the other PR.
        overlapping_ranges: Pairs of (target_range, other_range) that overlap.
    """

    file_path: str
    has_line_overlap: bool | None = None
    target_lines: list[LineRange] = field(default_factory=list)
    other_lines: list[LineRange] = field(default_factory=list)
    overlapping_ranges: list[tuple[LineRange, LineRange]] = field(default_factory=list)


@dataclass(frozen=True)
class ConflictResult:
    """
    Result of comparing a target PR against a single other PR.

    Frozen to ensure immutability — once computed, results cannot
    be accidentally modified.
    """

    pr_number: int
    pr_title: str
    pr_author: str
    pr_url: str
    overlapping_files: list[str]
    overlap_count: int
    risk_level: str
    file_details: list[FileOverlapDetail] = field(default_factory=list)


def classify_risk(overlap_count: int) -> str:
    """
    Classify the conflict risk level based on the number of overlapping files.

    Thresholds are defined in constants.py:
        ≥ HIGH_RISK_THRESHOLD (3) → HIGH
        ≥ MEDIUM_RISK_THRESHOLD (2) → MEDIUM
        1 → LOW
    """
    if overlap_count >= HIGH_RISK_THRESHOLD:
        return RISK_HIGH
    if overlap_count >= MEDIUM_RISK_THRESHOLD:
        return RISK_MEDIUM
    return RISK_LOW


def classify_risk_with_lines(
    overlap_count: int,
    file_details: list[FileOverlapDetail],
) -> str:
    """
    Classify risk using line-level data when available.

    Only files with actual line overlap (or unknown line status)
    contribute to the effective overlap count. Files where line-level
    analysis proves no overlap are excluded.

    Falls back to plain file-count classification when no line data exists.
    """
    if not file_details:
        return classify_risk(overlap_count)

    # Count files that have confirmed line overlap or unknown status.
    effective_count = sum(
        1 for d in file_details if d.has_line_overlap is not False
    )

    if effective_count == 0:
        # All files were analyzed at line level and none overlap.
        # Still return LOW since file-level overlap exists.
        return RISK_LOW

    return classify_risk(effective_count)


def detect_conflicts(
    target_files: set[str],
    other_prs: list[dict[str, Any]],
) -> list[ConflictResult]:
    """
    Detect file-level conflicts between the target PR and all other open PRs.

    Args:
        target_files: Set of file paths changed in the target PR.
        other_prs: List of dicts, each containing:
            - "number": PR number (int)
            - "title": PR title (str)
            - "author": PR author login (str)
            - "url": PR HTML URL (str)
            - "files": Set of file paths changed in this PR (set[str])

    Returns:
        List of ConflictResult for PRs with at least one overlapping file,
        sorted by overlap_count descending (highest risk first).
    """
    conflicts: list[ConflictResult] = []

    for pr_data in other_prs:
        other_files = pr_data["files"]
        overlapping = target_files & other_files

        if not overlapping:
            continue

        overlap_count = len(overlapping)
        conflicts.append(
            ConflictResult(
                pr_number=pr_data["number"],
                pr_title=pr_data["title"],
                pr_author=pr_data["author"],
                pr_url=pr_data["url"],
                overlapping_files=sorted(overlapping),
                overlap_count=overlap_count,
                risk_level=classify_risk(overlap_count),
            )
        )

    # Sort by overlap_count descending — highest risk first.
    conflicts.sort(key=lambda c: c.overlap_count, reverse=True)
    return conflicts


def detect_conflicts_with_lines(
    target_files: set[str],
    other_prs: list[dict[str, Any]],
    target_patches: dict[str, str | None],
    other_patches: dict[int, dict[str, str | None]],
) -> list[ConflictResult]:
    """
    Detect conflicts with line-level overlap analysis.

    Extends file-level detection by parsing unified diff patches and
    checking whether the changed line ranges actually overlap.

    Args:
        target_files: Set of file paths changed in the target PR.
        other_prs: Same format as detect_conflicts().
        target_patches: Mapping of {filename: patch_text} for the target PR.
                        patch_text may be None for binary files or large diffs.
        other_patches: Mapping of {pr_number: {filename: patch_text}} for
                       each other PR.

    Returns:
        List of ConflictResult with file_details populated.
        Falls back to file-level detection for files where patches are
        unavailable or unparseable.
    """
    conflicts: list[ConflictResult] = []

    for pr_data in other_prs:
        other_files = pr_data["files"]
        overlapping = target_files & other_files

        if not overlapping:
            continue

        pr_number = pr_data["number"]
        pr_patches = other_patches.get(pr_number, {})
        file_details: list[FileOverlapDetail] = []

        for file_path in sorted(overlapping):
            target_patch = target_patches.get(file_path)
            other_patch = pr_patches.get(file_path)

            target_ranges = parse_patch(target_patch)
            other_ranges = parse_patch(other_patch)

            # If either side has no parseable ranges, fall back.
            if not target_ranges or not other_ranges:
                file_details.append(
                    FileOverlapDetail(
                        file_path=file_path,
                        has_line_overlap=None,
                        target_lines=target_ranges,
                        other_lines=other_ranges,
                    )
                )
                logger.debug(
                    "No patch data for %s in PR #%d — file-level fallback",
                    file_path,
                    pr_number,
                )
                continue

            overlaps = ranges_overlap(target_ranges, other_ranges)
            file_details.append(
                FileOverlapDetail(
                    file_path=file_path,
                    has_line_overlap=len(overlaps) > 0,
                    target_lines=target_ranges,
                    other_lines=other_ranges,
                    overlapping_ranges=overlaps,
                )
            )

        overlap_count = len(overlapping)
        conflicts.append(
            ConflictResult(
                pr_number=pr_data["number"],
                pr_title=pr_data["title"],
                pr_author=pr_data["author"],
                pr_url=pr_data["url"],
                overlapping_files=sorted(overlapping),
                overlap_count=overlap_count,
                risk_level=classify_risk_with_lines(overlap_count, file_details),
                file_details=file_details,
            )
        )

    # Sort by overlap_count descending — highest risk first.
    conflicts.sort(key=lambda c: c.overlap_count, reverse=True)
    return conflicts
