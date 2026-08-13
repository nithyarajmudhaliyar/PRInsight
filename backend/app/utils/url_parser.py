"""
GitHub URL validation and component extraction.

Pure functions with no side effects. Fully unit-testable.
"""

import re
from dataclasses import dataclass

from app.core.constants import GITHUB_PR_URL_PATTERN
from app.exceptions.validation import InvalidPRURLError

# Compile the regex once at module load.
_PR_URL_REGEX = re.compile(GITHUB_PR_URL_PATTERN)


@dataclass(frozen=True)
class PRComponents:
    """
    Extracted components from a GitHub Pull Request URL.

    Frozen dataclass ensures immutability — once parsed, the data
    cannot be accidentally modified downstream.
    """

    owner: str
    repo: str
    number: int


def parse_pr_url(url: str) -> PRComponents:
    """
    Validate and extract components from a GitHub Pull Request URL.

    Args:
        url: A full GitHub Pull Request URL, e.g.
             https://github.com/facebook/react/pull/12345

    Returns:
        PRComponents with owner, repo, and PR number.

    Raises:
        InvalidPRURLError: If the URL does not match the expected format.
    """
    url = url.strip()
    match = _PR_URL_REGEX.match(url)

    if not match:
        raise InvalidPRURLError(url)

    return PRComponents(
        owner=match.group("owner"),
        repo=match.group("repo"),
        number=int(match.group("number")),
    )


def normalize_pr_url(url: str) -> str:
    """
    Normalize a PR URL for use as a cache key.

    Strips whitespace, lowercases, and removes trailing slashes.
    This ensures that variations of the same URL resolve to the
    same cache entry.
    """
    return url.strip().lower().rstrip("/")
