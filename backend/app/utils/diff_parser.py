"""
Unified diff parser for extracting changed line ranges.

Pure-function module with zero I/O dependencies. Parses patch text
returned by the GitHub API (unified diff format) and extracts the
exact line positions that were changed by walking through the actual
``+`` and ``-`` diff lines.

Changed positions are tracked in old-file (base) coordinates so that
changes from two different PRs — both branching from the same base —
can be directly compared in a common reference frame.

This module is the foundation for line-level conflict detection.
"""

import logging
import re
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Matches unified diff hunk headers: @@ -a,b +c,d @@
# The count (b/d) is optional — when omitted, it implies 1 line.
_HUNK_HEADER_RE = re.compile(
    r"^@@\s+"
    r"-(\d+)(?:,(\d+))?\s+"
    r"\+(\d+)(?:,(\d+))?\s+"
    r"@@"
)


class LineRange(NamedTuple):
    """Inclusive line range (start, end) in a file."""

    start: int
    end: int


def _consolidate_ranges(positions: list[int]) -> list[LineRange]:
    """
    Convert a sorted list of unique line positions into contiguous LineRange objects.

    Adjacent positions are merged: [5, 6, 7, 12, 13] → [LineRange(5,7), LineRange(12,13)].
    """
    if not positions:
        return []

    ranges: list[LineRange] = []
    start = positions[0]
    end = positions[0]

    for pos in positions[1:]:
        if pos == end + 1:
            end = pos
        else:
            ranges.append(LineRange(start=start, end=end))
            start = pos
            end = pos

    ranges.append(LineRange(start=start, end=end))
    return ranges


def parse_patch(patch: str | None) -> list[LineRange]:
    """
    Parse a unified diff patch and extract changed line ranges.

    Walks through each hunk's diff lines to identify exactly which
    base-file lines are affected by the changes, rather than treating
    the entire hunk range as modified.

    Changed positions are tracked in old-file (base) coordinates:

    - **Deleted lines** (``-``): directly map to old-file positions.
    - **Modified lines** (``-`` followed by ``+``): the ``-`` lines
      record the affected old-file positions; the ``+`` lines are
      replacements and do not add extra positions.
    - **Pure insertions** (``+`` not following ``-``): map to the
      insertion point in the old file — the next unconsumed
      old-file line number.

    Using old-file coordinates provides a common reference frame for
    comparing changes from two PRs that both branch from the same base.

    Args:
        patch: Unified diff text (as returned by GitHub's ``patch`` field).
               May be None for binary files or large diffs.

    Returns:
        List of LineRange representing affected base-file line ranges.
        Returns an empty list if the patch is None, empty, or unparseable.
    """
    if not patch:
        return []

    changed_positions: set[int] = set()
    old_pos = 0
    new_pos = 0
    in_deletion = False
    in_hunk = False

    for line in patch.splitlines():
        match = _HUNK_HEADER_RE.match(line)
        if match:
            old_pos = int(match.group(1))
            new_pos = int(match.group(3))
            in_deletion = False
            in_hunk = True
            continue

        if not in_hunk:
            continue

        if line.startswith("-"):
            changed_positions.add(old_pos)
            old_pos += 1
            in_deletion = True
        elif line.startswith("+"):
            if not in_deletion:
                # Pure insertion — record the insertion point.
                changed_positions.add(old_pos)
            new_pos += 1
        elif line.startswith(" "):
            old_pos += 1
            new_pos += 1
            in_deletion = False
        elif line.startswith("\\"):
            # "\ No newline at end of file" — skip.
            pass

    return _consolidate_ranges(sorted(changed_positions))


def ranges_overlap(
    ranges_a: list[LineRange],
    ranges_b: list[LineRange],
) -> list[tuple[LineRange, LineRange]]:
    """
    Find all pairs of overlapping ranges between two lists.

    Two ranges overlap if they share at least one line number:
        a.start <= b.end AND b.start <= a.end

    Args:
        ranges_a: Line ranges from the first PR's changes.
        ranges_b: Line ranges from the second PR's changes.

    Returns:
        List of (range_from_a, range_from_b) tuples that overlap.
        Empty list if there is no overlap.
    """
    overlaps: list[tuple[LineRange, LineRange]] = []

    for a in ranges_a:
        for b in ranges_b:
            if a.start <= b.end and b.start <= a.end:
                overlaps.append((a, b))

    return overlaps
