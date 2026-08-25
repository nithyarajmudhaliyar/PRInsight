"""
Unit tests for app.utils.diff_parser.

Tests cover:
    - Single-line and multi-line modifications
    - Pure insertions (no deletions)
    - Pure deletions (no insertions)
    - Separate changes within a single hunk
    - Multiple hunks
    - New file (all additions) and file deletion
    - Empty / None / malformed patches
    - No-newline-at-end-of-file marker
    - Consolidated contiguous ranges
    - Range overlap detection (no overlap, partial, full containment, adjacent)
"""

from app.utils.diff_parser import LineRange, parse_patch, ranges_overlap


class TestParsePatch:
    """Tests for parse_patch()."""

    def test_single_line_modification(self):
        """One line deleted and replaced → single affected position."""
        patch = (
            "@@ -10,3 +10,3 @@\n"
            " context before\n"
            "-old line\n"
            "+new line\n"
            " context after"
        )
        result = parse_patch(patch)
        assert result == [LineRange(start=11, end=11)]

    def test_multi_line_modification(self):
        """Multiple lines deleted and replaced."""
        patch = (
            "@@ -5,5 +5,5 @@\n"
            " context\n"
            "-old line A\n"
            "-old line B\n"
            "+new line A\n"
            "+new line B\n"
            " context"
        )
        result = parse_patch(patch)
        assert result == [LineRange(start=6, end=7)]

    def test_pure_insertion(self):
        """Lines added without deleting any → single insertion point."""
        patch = (
            "@@ -10,2 +10,4 @@\n"
            " context before\n"
            "+inserted line A\n"
            "+inserted line B\n"
            " context after"
        )
        result = parse_patch(patch)
        # All insertions are at the same old-file point.
        assert result == [LineRange(start=11, end=11)]

    def test_pure_deletion(self):
        """Lines deleted without adding any."""
        patch = (
            "@@ -10,4 +10,2 @@\n"
            " context before\n"
            "-deleted line A\n"
            "-deleted line B\n"
            " context after"
        )
        result = parse_patch(patch)
        assert result == [LineRange(start=11, end=12)]

    def test_separate_changes_within_one_hunk(self):
        """Two modifications within the same hunk separated by context."""
        patch = (
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
        result = parse_patch(patch)
        assert result == [LineRange(start=6, end=6), LineRange(start=9, end=9)]

    def test_multiple_hunks(self):
        """Changes across multiple hunks."""
        patch = (
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
        result = parse_patch(patch)
        assert result == [LineRange(start=6, end=6), LineRange(start=21, end=21)]

    def test_new_file_all_additions(self):
        """New file — old side is 0,0, all lines are additions."""
        patch = (
            "@@ -0,0 +1,3 @@\n"
            "+line 1\n"
            "+line 2\n"
            "+line 3"
        )
        result = parse_patch(patch)
        # All insertions at old_pos=0 (new file anchor).
        assert result == [LineRange(start=0, end=0)]

    def test_file_deletion(self):
        """Entire file deleted — all lines are deletions."""
        patch = (
            "@@ -1,3 +0,0 @@\n"
            "-line 1\n"
            "-line 2\n"
            "-line 3"
        )
        result = parse_patch(patch)
        assert result == [LineRange(start=1, end=3)]

    def test_none_patch(self):
        assert parse_patch(None) == []

    def test_empty_patch(self):
        assert parse_patch("") == []

    def test_no_hunk_headers(self):
        """Patch text without any @@ headers."""
        assert parse_patch("just some text\nwith no headers") == []

    def test_malformed_hunk_header(self):
        """Partial or broken header should be skipped."""
        assert parse_patch("@@ -1,5 @@\n broken") == []

    def test_no_newline_marker(self):
        r"""'\ No newline at end of file' is correctly skipped."""
        patch = (
            "@@ -1,3 +1,3 @@\n"
            " context\n"
            "-old line\n"
            "+new line\n"
            "\\ No newline at end of file"
        )
        result = parse_patch(patch)
        assert result == [LineRange(start=2, end=2)]

    def test_hunk_header_with_section_name(self):
        """GitHub often includes function/class name after @@."""
        patch = (
            "@@ -100,3 +100,3 @@ class MyClass:\n"
            " context\n"
            "-old method\n"
            "+new method\n"
            " context"
        )
        result = parse_patch(patch)
        assert result == [LineRange(start=101, end=101)]

    def test_single_line_hunk_count_omitted(self):
        """When count is omitted, it implies 1 line."""
        patch = (
            "@@ -10 +10 @@\n"
            "-old line\n"
            "+new line"
        )
        result = parse_patch(patch)
        assert result == [LineRange(start=10, end=10)]

    def test_insertion_at_file_start(self):
        """Insertion at the very beginning of the file."""
        patch = (
            "@@ -1,2 +1,4 @@\n"
            "+new line A\n"
            "+new line B\n"
            " existing line 1\n"
            " existing line 2"
        )
        result = parse_patch(patch)
        # Insertion at old_pos=1 (before existing line 1).
        assert result == [LineRange(start=1, end=1)]

    def test_modification_then_insertion(self):
        """A modification followed by a pure insertion in the same hunk."""
        patch = (
            "@@ -10,4 +10,5 @@\n"
            " context\n"
            "-old line 11\n"
            "+new line 11\n"
            " context 12\n"
            "+inserted after 12\n"
            " context 13"
        )
        result = parse_patch(patch)
        # Position 11: modification. Position 13: pure insertion point.
        assert result == [LineRange(start=11, end=11), LineRange(start=13, end=13)]

    def test_contiguous_positions_are_consolidated(self):
        """Adjacent changed positions are merged into one range."""
        patch = (
            "@@ -10,5 +10,5 @@\n"
            " context\n"
            "-old 11\n"
            "-old 12\n"
            "-old 13\n"
            "+new 11\n"
            "+new 12\n"
            "+new 13\n"
            " context"
        )
        result = parse_patch(patch)
        assert result == [LineRange(start=11, end=13)]


class TestRangesOverlap:
    """Tests for ranges_overlap()."""

    def test_no_overlap(self):
        a = [LineRange(1, 5)]
        b = [LineRange(10, 15)]
        assert ranges_overlap(a, b) == []

    def test_adjacent_ranges_no_overlap(self):
        """Ranges [1,5] and [6,10] are adjacent but don't share a line."""
        a = [LineRange(1, 5)]
        b = [LineRange(6, 10)]
        assert ranges_overlap(a, b) == []

    def test_single_line_overlap(self):
        """Ranges share exactly one line."""
        a = [LineRange(1, 5)]
        b = [LineRange(5, 10)]
        result = ranges_overlap(a, b)
        assert result == [(LineRange(1, 5), LineRange(5, 10))]

    def test_full_containment(self):
        """One range fully contains the other."""
        a = [LineRange(1, 20)]
        b = [LineRange(5, 10)]
        result = ranges_overlap(a, b)
        assert result == [(LineRange(1, 20), LineRange(5, 10))]

    def test_partial_overlap(self):
        a = [LineRange(1, 10)]
        b = [LineRange(8, 15)]
        result = ranges_overlap(a, b)
        assert result == [(LineRange(1, 10), LineRange(8, 15))]

    def test_identical_ranges(self):
        a = [LineRange(5, 10)]
        b = [LineRange(5, 10)]
        result = ranges_overlap(a, b)
        assert result == [(LineRange(5, 10), LineRange(5, 10))]

    def test_multiple_overlapping_pairs(self):
        a = [LineRange(1, 5), LineRange(10, 15)]
        b = [LineRange(3, 12)]
        result = ranges_overlap(a, b)
        assert len(result) == 2
        assert (LineRange(1, 5), LineRange(3, 12)) in result
        assert (LineRange(10, 15), LineRange(3, 12)) in result

    def test_empty_ranges_a(self):
        assert ranges_overlap([], [LineRange(1, 5)]) == []

    def test_empty_ranges_b(self):
        assert ranges_overlap([LineRange(1, 5)], []) == []

    def test_both_empty(self):
        assert ranges_overlap([], []) == []

    def test_multiple_ranges_no_overlap(self):
        a = [LineRange(1, 5), LineRange(20, 25)]
        b = [LineRange(10, 15), LineRange(30, 35)]
        assert ranges_overlap(a, b) == []

    def test_single_line_ranges_same_line(self):
        """Two single-line ranges on the same line."""
        a = [LineRange(10, 10)]
        b = [LineRange(10, 10)]
        assert ranges_overlap(a, b) == [(LineRange(10, 10), LineRange(10, 10))]
