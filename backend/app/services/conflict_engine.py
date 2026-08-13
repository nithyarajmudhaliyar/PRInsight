"""
Conflict detection engine.

Pure-logic module with zero I/O dependencies. Receives file data,
computes set intersections, and assigns risk levels.

This is the most critical business logic in the application and is
trivially unit-testable because it has no side effects.

Future migration path:
    Swapping in a more sophisticated algorithm (line-level analysis,
    semantic analysis, ML-based scoring) requires changing ONLY this file.
"""

from dataclasses import dataclass
from typing import Any

from app.core.constants import (
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
)


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
