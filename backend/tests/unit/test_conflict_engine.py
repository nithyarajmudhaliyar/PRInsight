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
from app.services.conflict_engine import classify_risk, detect_conflicts


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
