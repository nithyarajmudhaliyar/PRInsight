"""
Base exception classes for PRInsight.

All application exceptions inherit from PRInsightError so that
the centralized exception handler in handlers.py can catch them
with a single base type.
"""


class PRInsightError(Exception):
    """
    Base exception for all PRInsight application errors.

    Attributes:
        message: Human-readable error description, safe to return to clients.
        code: Machine-readable error code for frontend conditional logic.
    """

    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


class AnalysisError(PRInsightError):
    """Raised when the analysis workflow encounters an unexpected failure."""

    def __init__(self, message: str = "An error occurred during analysis.") -> None:
        super().__init__(message=message, code="ANALYSIS_ERROR")
