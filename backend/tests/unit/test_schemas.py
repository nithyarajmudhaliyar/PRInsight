"""
Unit tests for app.schemas (request and response models).

Tests cover:
    - AnalyzeRequest validation (valid input, missing fields, empty strings)
    - Response model serialization
    - RiskLevel enum values
    - ErrorResponse structure
"""

import pytest
from pydantic import ValidationError

from app.schemas.common import ErrorDetail, ErrorResponse, RiskLevel
from app.schemas.requests import AnalyzeRequest


class TestAnalyzeRequest:
    """Tests for AnalyzeRequest schema."""

    def test_valid_request(self):
        req = AnalyzeRequest(pr_url="https://github.com/owner/repo/pull/1")
        assert req.pr_url == "https://github.com/owner/repo/pull/1"

    def test_missing_pr_url_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest()

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(pr_url="")

    def test_whitespace_only_raises(self):
        """min_length=1 should reject whitespace-only after Pydantic's strip."""
        with pytest.raises(ValidationError):
            AnalyzeRequest(pr_url="   ")

    def test_accepts_any_string_format(self):
        """Schema only checks type and min_length. URL format validation is in url_parser."""
        req = AnalyzeRequest(pr_url="not-a-url-but-valid-string")
        assert req.pr_url == "not-a-url-but-valid-string"


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_high_value(self):
        assert RiskLevel.HIGH == "high"

    def test_medium_value(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_low_value(self):
        assert RiskLevel.LOW == "low"

    def test_is_string_enum(self):
        assert isinstance(RiskLevel.HIGH, str)


class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_error_response_structure(self):
        resp = ErrorResponse(
            error=ErrorDetail(
                code="TEST_ERROR",
                message="Something went wrong.",
            )
        )
        assert resp.status == "error"
        assert resp.error.code == "TEST_ERROR"
        assert resp.error.message == "Something went wrong."
        assert resp.error.details is None

    def test_error_response_with_details(self):
        resp = ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Invalid input.",
                details={"field": "pr_url", "error": "required"},
            )
        )
        assert resp.error.details == {"field": "pr_url", "error": "required"}
