"""
Unit tests for app.services.conflict_engine.

Tests cover:
    - No conflicts (disjoint file sets)
    - Single file overlap (LOW risk)
    - Two file overlap (MEDIUM risk)
    - Three+ file overlap (HIGH risk)
    - Multiple conflicting PRs
    - Identical file sets
    - Empty file sets
    - Sorting order (highest overlap first)
    - Risk classification function
"""

from app.core.constants import RISK_HIGH, RISK_LOW, RISK_MEDIUM
from app.services.conflict_engine import (
    FileOverlapDetail,
    classify_risk,
    classify_risk_with_lines,
    detect_conflicts,
    detect_conflicts_with_lines,
)


class TestClassifyRisk:
    """Tests for classify_risk()."""

    def test_one_file_is_low(self):
        assert classify_risk(1) == RISK_LOW

    def test_two_files_is_medium(self):
        assert classify_risk(2) == RISK_MEDIUM

    def test_three_files_is_high(self):
        assert classify_risk(3) == RISK_HIGH

    def test_ten_files_is_high(self):
        assert classify_risk(10) == RISK_HIGH


class TestDetectConflicts:
    """Tests for detect_conflicts()."""

    def _make_pr(self, number: int, files: set[str]) -> dict:
        """Helper to create a PR data dict for testing."""
        return {
            "number": number,
            "title": f"PR #{number}",
            "author": f"dev-{number}",
            "url": f"https://github.com/owner/repo/pull/{number}",
            "files": files,
        }

    def test_no_conflicts_disjoint_files(self):
        target_files = {"a.py", "b.py"}
        other_prs = [self._make_pr(2, {"c.py", "d.py"})]
        result = detect_conflicts(target_files, other_prs)
        assert result == []

    def test_no_conflicts_empty_other_prs(self):
        target_files = {"a.py", "b.py"}
        result = detect_conflicts(target_files, [])
        assert result == []

    def test_no_conflicts_empty_target_files(self):
        other_prs = [self._make_pr(2, {"a.py"})]
        result = detect_conflicts(set(), other_prs)
        assert result == []

    def test_single_overlap_low_risk(self):
        target_files = {"a.py", "b.py"}
        other_prs = [self._make_pr(2, {"a.py", "c.py"})]
        result = detect_conflicts(target_files, other_prs)

        assert len(result) == 1
        assert result[0].pr_number == 2
        assert result[0].overlapping_files == ["a.py"]
        assert result[0].overlap_count == 1
        assert result[0].risk_level == RISK_LOW

    def test_two_overlaps_medium_risk(self):
        target_files = {"a.py", "b.py", "c.py"}
        other_prs = [self._make_pr(2, {"a.py", "b.py", "d.py"})]
        result = detect_conflicts(target_files, other_prs)

        assert len(result) == 1
        assert result[0].overlap_count == 2
        assert result[0].risk_level == RISK_MEDIUM

    def test_three_overlaps_high_risk(self):
        target_files = {"a.py", "b.py", "c.py"}
        other_prs = [self._make_pr(2, {"a.py", "b.py", "c.py"})]
        result = detect_conflicts(target_files, other_prs)

        assert len(result) == 1
        assert result[0].overlap_count == 3
        assert result[0].risk_level == RISK_HIGH

    def test_multiple_conflicting_prs(self):
        target_files = {"a.py", "b.py", "c.py"}
        other_prs = [
            self._make_pr(2, {"a.py"}),            # 1 overlap — LOW
            self._make_pr(3, {"a.py", "b.py"}),    # 2 overlaps — MEDIUM
            self._make_pr(4, {"d.py"}),             # 0 overlaps — no conflict
        ]
        result = detect_conflicts(target_files, other_prs)

        assert len(result) == 2  # PR 4 excluded
        # Sorted by overlap_count descending
        assert result[0].pr_number == 3
        assert result[0].overlap_count == 2
        assert result[1].pr_number == 2
        assert result[1].overlap_count == 1

    def test_identical_file_sets(self):
        target_files = {"a.py", "b.py", "c.py"}
        other_prs = [self._make_pr(2, {"a.py", "b.py", "c.py"})]
        result = detect_conflicts(target_files, other_prs)

        assert len(result) == 1
        assert result[0].overlap_count == 3
        assert sorted(result[0].overlapping_files) == ["a.py", "b.py", "c.py"]

    def test_overlapping_files_are_sorted(self):
        target_files = {"z.py", "a.py", "m.py"}
        other_prs = [self._make_pr(2, {"z.py", "a.py", "m.py"})]
        result = detect_conflicts(target_files, other_prs)

        assert result[0].overlapping_files == ["a.py", "m.py", "z.py"]

    def test_results_sorted_by_overlap_descending(self):
        target_files = {"a.py", "b.py", "c.py", "d.py"}
        other_prs = [
            self._make_pr(10, {"a.py"}),                       # 1
            self._make_pr(20, {"a.py", "b.py", "c.py"}),      # 3
            self._make_pr(30, {"a.py", "b.py"}),               # 2
        ]
        result = detect_conflicts(target_files, other_prs)

        assert [r.pr_number for r in result] == [20, 30, 10]

    def test_pr_metadata_is_preserved(self):
        target_files = {"a.py"}
        other_prs = [
            {
                "number": 42,
                "title": "Important PR",
                "author": "alice",
                "url": "https://github.com/owner/repo/pull/42",
                "files": {"a.py"},
            }
        ]
        result = detect_conflicts(target_files, other_prs)

        assert result[0].pr_number == 42
        assert result[0].pr_title == "Important PR"
        assert result[0].pr_author == "alice"
        assert result[0].pr_url == "https://github.com/owner/repo/pull/42"


class TestClassifyRiskWithLines:
    """Tests for classify_risk_with_lines()."""

    def test_empty_file_details_falls_back(self):
        """No file details → use plain file-count classification."""
        assert classify_risk_with_lines(3, []) == RISK_HIGH

    def test_all_files_have_line_overlap(self):
        """All overlapping files have confirmed line overlap."""
        details = [
            FileOverlapDetail(file_path="a.py", has_line_overlap=True),
            FileOverlapDetail(file_path="b.py", has_line_overlap=True),
            FileOverlapDetail(file_path="c.py", has_line_overlap=True),
        ]
        assert classify_risk_with_lines(3, details) == RISK_HIGH

    def test_no_files_have_line_overlap(self):
        """All files analyzed, none have line overlap → LOW."""
        details = [
            FileOverlapDetail(file_path="a.py", has_line_overlap=False),
            FileOverlapDetail(file_path="b.py", has_line_overlap=False),
            FileOverlapDetail(file_path="c.py", has_line_overlap=False),
        ]
        assert classify_risk_with_lines(3, details) == RISK_LOW

    def test_mixed_overlap_and_no_overlap(self):
        """Some files overlap, some don't — only overlapping count."""
        details = [
            FileOverlapDetail(file_path="a.py", has_line_overlap=True),
            FileOverlapDetail(file_path="b.py", has_line_overlap=False),
            FileOverlapDetail(file_path="c.py", has_line_overlap=True),
        ]
        # 2 files with line overlap → MEDIUM
        assert classify_risk_with_lines(3, details) == RISK_MEDIUM

    def test_unknown_line_status_counts(self):
        """Files with unknown status (None) count as potential overlap."""
        details = [
            FileOverlapDetail(file_path="a.py", has_line_overlap=None),
            FileOverlapDetail(file_path="b.py", has_line_overlap=False),
        ]
        # 1 unknown → counts → LOW
        assert classify_risk_with_lines(2, details) == RISK_LOW

    def test_single_file_no_line_overlap(self):
        details = [
            FileOverlapDetail(file_path="a.py", has_line_overlap=False),
        ]
        assert classify_risk_with_lines(1, details) == RISK_LOW


class TestDetectConflictsWithLines:
    """Tests for detect_conflicts_with_lines()."""

    def _make_pr(self, number: int, files: set[str]) -> dict:
        return {
            "number": number,
            "title": f"PR #{number}",
            "author": f"dev-{number}",
            "url": f"https://github.com/owner/repo/pull/{number}",
            "files": files,
        }

    # ── Patch helpers ────────────────────────────────────────────────

    @staticmethod
    def _modification_patch(old_line: int) -> str:
        """Patch that modifies a single line at the given old-file position."""
        s = old_line - 1
        return (
            f"@@ -{s},3 +{s},3 @@\n"
            " context\n"
            f"-old line {old_line}\n"
            f"+new line {old_line}\n"
            " context"
        )

    @staticmethod
    def _insertion_patch(after_old_line: int) -> str:
        """Patch that inserts a line after the given old-file line."""
        n = after_old_line + 1
        return (
            f"@@ -{after_old_line},2 +{after_old_line},3 @@\n"
            f" context line {after_old_line}\n"
            "+inserted line\n"
            f" context line {n}"
        )

    @staticmethod
    def _deletion_patch(old_line: int) -> str:
        """Patch that deletes a single line at the given old-file position."""
        s = old_line - 1
        return (
            f"@@ -{s},3 +{s},2 @@\n"
            " context\n"
            f"-deleted line {old_line}\n"
            " context"
        )

    # ── No overlap tests ────────────────────────────────────────────

    def test_no_file_overlap(self):
        """Disjoint file sets → no conflicts, no line analysis."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"b.py"})]
        result = detect_conflicts_with_lines(
            target_files, other_prs, {"a.py": None}, {2: {"b.py": None}}
        )
        assert result == []

    def test_same_file_different_lines(self):
        """Same file modified but on different lines → no line overlap."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": self._modification_patch(11)},
            {2: {"a.py": self._modification_patch(21)}},
        )

        assert len(result) == 1
        assert result[0].overlap_count == 1
        assert len(result[0].file_details) == 1
        detail = result[0].file_details[0]
        assert detail.file_path == "a.py"
        assert detail.has_line_overlap is False
        assert detail.overlapping_ranges == []
        assert result[0].risk_level == RISK_LOW

    def test_adjacent_but_non_overlapping(self):
        """Adjacent modified lines (11 and 12) do not overlap."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": self._modification_patch(11)},
            {2: {"a.py": self._modification_patch(12)}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is False

    # ── Overlap tests — conflict type matrix ────────────────────────

    def test_modification_vs_modification(self):
        """Both PRs modify the same line → confirmed overlap."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": self._modification_patch(11)},
            {2: {"a.py": self._modification_patch(11)}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is True
        assert len(detail.overlapping_ranges) == 1

    def test_addition_vs_addition(self):
        """Both PRs insert at the same position → conflict."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": self._insertion_patch(10)},
            {2: {"a.py": self._insertion_patch(10)}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is True

    def test_modification_vs_addition(self):
        """One PR modifies line 11, other inserts before it → conflict."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        # Modification of line 11 → affected position {11}
        # Insertion after line 10 → insertion point {11}
        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": self._modification_patch(11)},
            {2: {"a.py": self._insertion_patch(10)}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is True

    def test_deletion_vs_modification(self):
        """One PR deletes line 11, other modifies it → conflict."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": self._deletion_patch(11)},
            {2: {"a.py": self._modification_patch(11)}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is True

    def test_deletion_vs_deletion(self):
        """Both PRs delete the same line → conflict."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": self._deletion_patch(11)},
            {2: {"a.py": self._deletion_patch(11)}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is True

    # ── Multi-range / multi-hunk tests ──────────────────────────────

    def test_separate_changes_within_same_hunk(self):
        """Two changes in one hunk with non-overlapping other PR → no overlap."""
        target_patch = (
            "@@ -5,7 +5,7 @@\n"
            " context\n"
            "-old line 6\n"
            "+new line 6\n"
            " context 7\n"
            " context 8\n"
            "-old line 9\n"
            "+new line 9\n"
            " context"
        )
        # Other modifies line 8 — between target's changes at 6 and 9.
        other_patch = self._modification_patch(8)

        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": target_patch},
            {2: {"a.py": other_patch}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is False

    def test_multiple_hunks_partial_overlap(self):
        """Target has two hunks; other PR overlaps only the second."""
        target_patch = (
            "@@ -5,3 +5,3 @@\n"
            " context\n"
            "-old line 6\n"
            "+new line 6\n"
            " context\n"
            "@@ -20,3 +20,3 @@\n"
            " context\n"
            "-old line 21\n"
            "+new line 21\n"
            " context"
        )
        # Other modifies line 21 — overlaps target's second hunk.
        other_patch = self._modification_patch(21)

        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": target_patch},
            {2: {"a.py": other_patch}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is True
        assert len(detail.overlapping_ranges) == 1

    def test_multiple_overlapping_ranges(self):
        """Both PRs change two separate regions that both overlap."""
        target_patch = (
            "@@ -5,3 +5,3 @@\n"
            " context\n"
            "-old line 6\n"
            "+new line 6\n"
            " context\n"
            "@@ -20,3 +20,3 @@\n"
            " context\n"
            "-old line 21\n"
            "+new line 21\n"
            " context"
        )
        other_patch = (
            "@@ -5,3 +5,3 @@\n"
            " context\n"
            "-other line 6\n"
            "+replaced 6\n"
            " context\n"
            "@@ -20,3 +20,3 @@\n"
            " context\n"
            "-other line 21\n"
            "+replaced 21\n"
            " context"
        )

        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": target_patch},
            {2: {"a.py": other_patch}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is True
        assert len(detail.overlapping_ranges) == 2

    # ── Fallback tests ──────────────────────────────────────────────

    def test_patch_unavailable_fallback(self):
        """No patch for either side → file-level fallback."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": None},
            {2: {"a.py": None}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is None
        assert detail.target_lines == []
        assert detail.other_lines == []

    def test_target_patch_unavailable_other_available(self):
        """Target patch missing, other available → fallback."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": None},
            {2: {"a.py": self._modification_patch(11)}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is None

    def test_unparseable_patch_fallback(self):
        """Patch text that has no valid hunk headers → fallback."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": "not a valid patch"},
            {2: {"a.py": self._modification_patch(11)}},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is None

    def test_missing_pr_patches_dict(self):
        """Other PR has no entry in other_patches → fallback."""
        target_files = {"a.py"}
        other_prs = [self._make_pr(2, {"a.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": self._modification_patch(11)},
            {},
        )

        assert len(result) == 1
        detail = result[0].file_details[0]
        assert detail.has_line_overlap is None

    # ── Risk and sorting tests ──────────────────────────────────────

    def test_risk_downgraded_when_no_line_overlap(self):
        """3 files overlap at file-level, but none at line-level → LOW."""
        target_files = {"a.py", "b.py", "c.py"}
        other_prs = [self._make_pr(2, {"a.py", "b.py", "c.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {
                "a.py": self._modification_patch(11),
                "b.py": self._modification_patch(11),
                "c.py": self._modification_patch(11),
            },
            {
                2: {
                    "a.py": self._modification_patch(21),
                    "b.py": self._modification_patch(21),
                    "c.py": self._modification_patch(21),
                }
            },
        )

        assert len(result) == 1
        assert result[0].overlap_count == 3
        assert result[0].risk_level == RISK_LOW

    def test_results_sorted_by_overlap_descending(self):
        target_files = {"a.py", "b.py", "c.py"}
        other_prs = [
            self._make_pr(10, {"a.py"}),
            self._make_pr(20, {"a.py", "b.py", "c.py"}),
        ]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": None, "b.py": None, "c.py": None},
            {10: {"a.py": None}, 20: {"a.py": None, "b.py": None, "c.py": None}},
        )

        assert result[0].pr_number == 20
        assert result[1].pr_number == 10

    def test_file_details_only_for_overlapping_files(self):
        """file_details should only contain files that actually overlap."""
        target_files = {"a.py", "b.py"}
        other_prs = [self._make_pr(2, {"a.py", "c.py"})]

        result = detect_conflicts_with_lines(
            target_files,
            other_prs,
            {"a.py": self._modification_patch(11), "b.py": self._modification_patch(11)},
            {2: {"a.py": self._modification_patch(11), "c.py": self._modification_patch(11)}},
        )

        assert len(result) == 1
        assert len(result[0].file_details) == 1
        assert result[0].file_details[0].file_path == "a.py"


