"""
Shared test fixtures for PRInsight backend tests.

Provides reusable fixtures for:
    - Application settings with test overrides
    - FastAPI TestClient
    - Mocked GitHubClient
    - TTLCache instances
    - Static test data from fixtures/
"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.cache.memory import TTLCache
from app.core.config import Settings

# Set GITHUB_TOKEN for test environment before importing app.
os.environ.setdefault("GITHUB_TOKEN", "ghp_test_token_for_testing")

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def test_settings() -> Settings:
    """Settings configured for testing."""
    return Settings(
        GITHUB_TOKEN="ghp_test_token_for_testing",
        DEBUG=True,
        LOG_LEVEL="DEBUG",
        CACHE_TTL_SECONDS=60,
        CACHE_MAX_ENTRIES=10,
        MAX_CONCURRENT_REQUESTS=2,
        MAX_PRS_TO_ANALYZE=100,
    )


@pytest.fixture
def test_cache() -> TTLCache:
    """Fresh TTLCache for each test."""
    return TTLCache(ttl=60, max_entries=10)


@pytest.fixture
def pr_response_data() -> dict:
    """Load the PR response fixture."""
    with open(FIXTURES_DIR / "pr_response.json") as f:
        return json.load(f)


@pytest.fixture
def files_response_data() -> list:
    """Load the files response fixture."""
    with open(FIXTURES_DIR / "files_response.json") as f:
        return json.load(f)


@pytest.fixture
def mock_github_client(pr_response_data, files_response_data):
    """
    A fully mocked GitHubClient with preset return values.

    By default:
        - get_pull_request → returns pr_response_data
        - get_pull_request_files → returns files_response_data
        - get_open_pull_requests → returns empty list (no other PRs)
    """
    client = AsyncMock()
    client.get_pull_request.return_value = pr_response_data
    client.get_pull_request_files.return_value = files_response_data
    client.get_open_pull_requests.return_value = []
    client.close.return_value = None
    return client


@pytest.fixture
def test_client() -> TestClient:
    """
    FastAPI TestClient for integration tests.

    Imports the app after environment variables are set.
    """
    from app.main import app
    return TestClient(app)
