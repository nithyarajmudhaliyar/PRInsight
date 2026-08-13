"""
Unit tests for app.utils.url_parser.

Tests cover:
    - Valid GitHub PR URLs in various formats
    - Invalid URLs (wrong domain, wrong path, missing parts)
    - Edge cases (trailing slash, query params, whitespace)
    - URL normalization for cache keys
"""

import pytest

from app.exceptions.validation import InvalidPRURLError
from app.utils.url_parser import PRComponents, normalize_pr_url, parse_pr_url


class TestParsePRUrl:
    """Tests for parse_pr_url()."""

    def test_valid_standard_url(self):
        result = parse_pr_url("https://github.com/facebook/react/pull/12345")
        assert result == PRComponents(owner="facebook", repo="react", number=12345)

    def test_valid_url_with_trailing_slash(self):
        result = parse_pr_url("https://github.com/facebook/react/pull/12345/")
        assert result == PRComponents(owner="facebook", repo="react", number=12345)

    def test_valid_url_with_whitespace(self):
        result = parse_pr_url("  https://github.com/facebook/react/pull/12345  ")
        assert result == PRComponents(owner="facebook", repo="react", number=12345)

    def test_valid_url_with_hyphenated_owner(self):
        result = parse_pr_url("https://github.com/my-org/my-repo/pull/1")
        assert result == PRComponents(owner="my-org", repo="my-repo", number=1)

    def test_valid_url_with_dotted_repo(self):
        result = parse_pr_url("https://github.com/owner/repo.js/pull/42")
        assert result == PRComponents(owner="owner", repo="repo.js", number=42)

    def test_valid_url_with_underscore_repo(self):
        result = parse_pr_url("https://github.com/owner/my_repo/pull/100")
        assert result == PRComponents(owner="owner", repo="my_repo", number=100)

    def test_extracts_correct_number(self):
        result = parse_pr_url("https://github.com/a/b/pull/99999")
        assert result.number == 99999

    def test_invalid_empty_string(self):
        with pytest.raises(InvalidPRURLError):
            parse_pr_url("")

    def test_invalid_random_text(self):
        with pytest.raises(InvalidPRURLError):
            parse_pr_url("not a url at all")

    def test_invalid_wrong_domain(self):
        with pytest.raises(InvalidPRURLError):
            parse_pr_url("https://gitlab.com/owner/repo/pull/1")

    def test_invalid_missing_pull_segment(self):
        with pytest.raises(InvalidPRURLError):
            parse_pr_url("https://github.com/owner/repo/1")

    def test_invalid_missing_number(self):
        with pytest.raises(InvalidPRURLError):
            parse_pr_url("https://github.com/owner/repo/pull/")

    def test_invalid_non_numeric_number(self):
        with pytest.raises(InvalidPRURLError):
            parse_pr_url("https://github.com/owner/repo/pull/abc")

    def test_invalid_issues_url(self):
        with pytest.raises(InvalidPRURLError):
            parse_pr_url("https://github.com/owner/repo/issues/123")

    def test_invalid_http_protocol(self):
        with pytest.raises(InvalidPRURLError):
            parse_pr_url("http://github.com/owner/repo/pull/1")

    def test_error_contains_url(self):
        bad_url = "https://example.com/not/valid"
        with pytest.raises(InvalidPRURLError) as exc_info:
            parse_pr_url(bad_url)
        assert bad_url in str(exc_info.value.message)
        assert exc_info.value.code == "INVALID_PR_URL"


class TestNormalizePRUrl:
    """Tests for normalize_pr_url()."""

    def test_lowercase(self):
        result = normalize_pr_url("https://GitHub.com/Owner/Repo/pull/1")
        assert result == "https://github.com/owner/repo/pull/1"

    def test_strips_trailing_slash(self):
        result = normalize_pr_url("https://github.com/owner/repo/pull/1/")
        assert result == "https://github.com/owner/repo/pull/1"

    def test_strips_whitespace(self):
        result = normalize_pr_url("  https://github.com/owner/repo/pull/1  ")
        assert result == "https://github.com/owner/repo/pull/1"

    def test_identical_urls_normalize_same(self):
        url1 = normalize_pr_url("https://github.com/Facebook/React/pull/123/")
        url2 = normalize_pr_url("  https://github.com/facebook/react/pull/123  ")
        assert url1 == url2
