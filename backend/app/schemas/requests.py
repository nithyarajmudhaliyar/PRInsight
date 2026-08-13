"""
Inbound request models.

These models are used as type annotations on FastAPI route handlers.
Pydantic automatically validates the incoming JSON body against them.
"""

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    """
    Request body for the POST /api/v1/analyze endpoint.

    The pr_url field accepts a full GitHub Pull Request URL.
    Structural validation (regex match) is performed by the url_parser
    utility in the service layer, not here — keeping schema validation
    limited to type/presence checks and format-level constraints.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    pr_url: str = Field(
        ...,
        min_length=1,
        description="Full GitHub Pull Request URL, e.g. https://github.com/owner/repo/pull/123",
        examples=["https://github.com/facebook/react/pull/12345"],
    )
