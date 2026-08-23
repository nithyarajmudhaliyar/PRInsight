"""
Unit tests for AuthService.

Tests session management, state validation, and error handling
without making real HTTP requests.
"""

import time
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.exceptions.auth import AuthenticationError, OAuthError, OAuthNotConfiguredError
from app.services.auth_service import AuthService


@pytest.fixture
def auth_settings() -> Settings:
    """Settings configured for auth testing with OAuth enabled."""
    return Settings(
        GITHUB_TOKEN="ghp_test_token",
        GITHUB_OAUTH_CLIENT_ID="test_client_id",
        GITHUB_OAUTH_CLIENT_SECRET="test_client_secret",
        GITHUB_OAUTH_REDIRECT_URI="http://localhost:8000/api/v1/auth/github/callback",
        FRONTEND_URL="http://localhost:5173",
        SESSION_TTL_SECONDS=3600,
    )


@pytest.fixture
def auth_settings_no_oauth() -> Settings:
    """Settings without OAuth configured."""
    return Settings(
        GITHUB_TOKEN="ghp_test_token",
        GITHUB_OAUTH_CLIENT_ID="",
        GITHUB_OAUTH_CLIENT_SECRET="",
    )


@pytest.fixture
def mock_oauth_client():
    """Mocked GitHubOAuthClient."""
    client = AsyncMock()
    client.exchange_code_for_token.return_value = "gho_test_access_token"
    client.get_user_profile.return_value = {
        "id": 12345,
        "login": "testuser",
        "name": "Test User",
        "avatar_url": "https://avatars.githubusercontent.com/u/12345",
    }
    return client


@pytest.fixture
def auth_service(mock_oauth_client, auth_settings) -> AuthService:
    """AuthService with mocked dependencies."""
    return AuthService(oauth_client=mock_oauth_client, settings=auth_settings)


@pytest.fixture
def auth_service_no_oauth(mock_oauth_client, auth_settings_no_oauth) -> AuthService:
    """AuthService with OAuth not configured."""
    return AuthService(oauth_client=mock_oauth_client, settings=auth_settings_no_oauth)


class TestCreateLoginUrl:
    """Tests for AuthService.create_login_url."""

    def test_generates_authorization_url(self, auth_service):
        url, state = auth_service.create_login_url()
        assert "github.com/login/oauth/authorize" in url
        assert "client_id=test_client_id" in url
        assert f"state={state}" in url

    def test_generates_unique_state(self, auth_service):
        _, state1 = auth_service.create_login_url()
        _, state2 = auth_service.create_login_url()
        assert state1 != state2

    def test_stores_state_for_validation(self, auth_service):
        _, state = auth_service.create_login_url()
        assert state in auth_service._oauth_states

    def test_raises_when_oauth_not_configured(self, auth_service_no_oauth):
        with pytest.raises(OAuthNotConfiguredError):
            auth_service_no_oauth.create_login_url()

    def test_requests_read_user_scope(self, auth_service):
        url, _ = auth_service.create_login_url()
        assert "scope=read" in url


class TestValidateState:
    """Tests for AuthService.validate_state."""

    def test_valid_state_passes(self, auth_service):
        _, state = auth_service.create_login_url()
        # Should not raise
        auth_service.validate_state(state)

    def test_state_is_consumed(self, auth_service):
        _, state = auth_service.create_login_url()
        auth_service.validate_state(state)
        # Second validation should fail (single-use)
        with pytest.raises(OAuthError, match="Invalid"):
            auth_service.validate_state(state)

    def test_invalid_state_raises(self, auth_service):
        with pytest.raises(OAuthError, match="Invalid"):
            auth_service.validate_state("nonexistent_state")

    def test_empty_state_raises(self, auth_service):
        with pytest.raises(OAuthError, match="Missing"):
            auth_service.validate_state("")

    def test_expired_state_raises(self, auth_service):
        _, state = auth_service.create_login_url()
        # Manually expire the state
        auth_service._oauth_states[state] = time.time() - 1
        with pytest.raises(OAuthError, match="expired"):
            auth_service.validate_state(state)


class TestHandleCallback:
    """Tests for AuthService.handle_callback."""

    async def test_successful_callback_creates_session(self, auth_service):
        _, state = auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="valid_code", state=state)
        assert session_id is not None
        assert len(auth_service._sessions) == 1

    async def test_session_contains_user_data(self, auth_service):
        _, state = auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="valid_code", state=state)
        session = auth_service._sessions[session_id]
        assert session["user"]["login"] == "testuser"
        assert session["user"]["id"] == 12345

    async def test_missing_code_raises(self, auth_service):
        _, state = auth_service.create_login_url()
        with pytest.raises(OAuthError, match="Missing authorization code"):
            await auth_service.handle_callback(code="", state=state)

    async def test_invalid_state_raises(self, auth_service):
        with pytest.raises(OAuthError, match="Invalid"):
            await auth_service.handle_callback(code="valid_code", state="bad_state")

    async def test_raises_when_oauth_not_configured(self, auth_service_no_oauth):
        with pytest.raises(OAuthNotConfiguredError):
            await auth_service_no_oauth.handle_callback(code="code", state="state")


class TestGetCurrentUser:
    """Tests for AuthService.get_current_user."""

    async def test_returns_user_for_valid_session(self, auth_service):
        _, state = auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="code", state=state)
        user = auth_service.get_current_user(session_id)
        assert user["login"] == "testuser"

    def test_raises_for_missing_session_id(self, auth_service):
        with pytest.raises(AuthenticationError):
            auth_service.get_current_user(None)

    def test_raises_for_invalid_session_id(self, auth_service):
        with pytest.raises(AuthenticationError):
            auth_service.get_current_user("nonexistent_session")

    async def test_raises_for_expired_session(self, auth_service):
        _, state = auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="code", state=state)
        # Manually expire the session
        auth_service._sessions[session_id]["expires_at"] = time.time() - 1
        with pytest.raises(AuthenticationError, match="expired"):
            auth_service.get_current_user(session_id)


class TestLogout:
    """Tests for AuthService.logout."""

    async def test_logout_removes_session(self, auth_service):
        _, state = auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="code", state=state)
        assert len(auth_service._sessions) == 1
        auth_service.logout(session_id)
        assert len(auth_service._sessions) == 0

    def test_logout_with_no_session_is_safe(self, auth_service):
        # Should not raise
        auth_service.logout(None)
        auth_service.logout("nonexistent")

    async def test_user_not_found_after_logout(self, auth_service):
        _, state = auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="code", state=state)
        auth_service.logout(session_id)
        with pytest.raises(AuthenticationError):
            auth_service.get_current_user(session_id)
