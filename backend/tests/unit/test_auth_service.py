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


class MockSessionStore:
    def __init__(self):
        self.sessions = {}
        self.oauth_states = {}
        
    async def save_session(self, session_id, data, ttl_seconds):
        self.sessions[session_id] = data
        
    async def get_session(self, session_id):
        return self.sessions.get(session_id)
        
    async def delete_session(self, session_id):
        self.sessions.pop(session_id, None)

    async def save_oauth_state(self, state: str, ttl_seconds: int):
        self.oauth_states[state] = time.time() + ttl_seconds

    async def consume_oauth_state(self, state: str) -> bool:
        if state not in self.oauth_states:
            return False
        expiry = self.oauth_states.pop(state)
        return time.time() <= expiry


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
    service = AuthService(oauth_client=mock_oauth_client, settings=auth_settings)
    service._session_store = MockSessionStore()
    return service


@pytest.fixture
def auth_service_no_oauth(mock_oauth_client, auth_settings_no_oauth) -> AuthService:
    """AuthService with OAuth not configured."""
    service = AuthService(oauth_client=mock_oauth_client, settings=auth_settings_no_oauth)
    service._session_store = MockSessionStore()
    return service


class TestCreateLoginUrl:
    """Tests for AuthService.create_login_url."""

    async def test_generates_authorization_url(self, auth_service):
        url, state = await auth_service.create_login_url()
        assert "github.com/login/oauth/authorize" in url
        assert "client_id=test_client_id" in url
        assert f"state={state}" in url

    async def test_generates_unique_state(self, auth_service):
        _, state1 = await auth_service.create_login_url()
        _, state2 = await auth_service.create_login_url()
        assert state1 != state2

    async def test_stores_state_for_validation(self, auth_service):
        _, state = await auth_service.create_login_url()
        assert state in auth_service._session_store.oauth_states

    async def test_raises_when_oauth_not_configured(self, auth_service_no_oauth):
        with pytest.raises(OAuthNotConfiguredError):
            await auth_service_no_oauth.create_login_url()

    async def test_requests_read_user_scope(self, auth_service):
        url, _ = await auth_service.create_login_url()
        assert "scope=read" in url


class TestValidateState:
    """Tests for AuthService.validate_state."""

    async def test_valid_state_passes(self, auth_service):
        _, state = await auth_service.create_login_url()
        # Should not raise
        await auth_service.validate_state(state)

    async def test_state_is_consumed(self, auth_service):
        _, state = await auth_service.create_login_url()
        await auth_service.validate_state(state)
        # Second validation should fail (single-use)
        with pytest.raises(OAuthError, match="Invalid or expired"):
            await auth_service.validate_state(state)

    async def test_invalid_state_raises(self, auth_service):
        with pytest.raises(OAuthError, match="Invalid or expired"):
            await auth_service.validate_state("nonexistent_state")

    async def test_empty_state_raises(self, auth_service):
        with pytest.raises(OAuthError, match="Missing"):
            await auth_service.validate_state("")

    async def test_expired_state_raises(self, auth_service):
        _, state = await auth_service.create_login_url()
        # Manually expire the state
        auth_service._session_store.oauth_states[state] = time.time() - 1
        with pytest.raises(OAuthError, match="expired"):
            await auth_service.validate_state(state)

    async def test_state_validation_across_independent_instances(self, mock_oauth_client, auth_settings):
        """State created by Instance A must be valid and consumable by Instance B."""
        shared_store = MockSessionStore()
        instance_a = AuthService(oauth_client=mock_oauth_client, settings=auth_settings)
        instance_a._session_store = shared_store
        instance_b = AuthService(oauth_client=mock_oauth_client, settings=auth_settings)
        instance_b._session_store = shared_store

        _, state = await instance_a.create_login_url()
        # Instance B validates and consumes the state
        await instance_b.validate_state(state)

        # Subsequent validation from any instance fails (single-use)
        with pytest.raises(OAuthError, match="Invalid or expired"):
            await instance_a.validate_state(state)
        with pytest.raises(OAuthError, match="Invalid or expired"):
            await instance_b.validate_state(state)

    async def test_callback_across_independent_instances(self, mock_oauth_client, auth_settings):
        """Login on Instance A followed by callback on Instance B succeeds."""
        shared_store = MockSessionStore()
        instance_a = AuthService(oauth_client=mock_oauth_client, settings=auth_settings)
        instance_a._session_store = shared_store
        instance_b = AuthService(oauth_client=mock_oauth_client, settings=auth_settings)
        instance_b._session_store = shared_store

        _, state = await instance_a.create_login_url()
        session_id = await instance_b.handle_callback(code="valid_code", state=state)
        assert session_id is not None
        assert session_id in shared_store.sessions


class TestHandleCallback:
    """Tests for AuthService.handle_callback."""

    async def test_successful_callback_creates_session(self, auth_service):
        _, state = await auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="valid_code", state=state)
        assert session_id is not None
        assert len(auth_service._session_store.sessions) == 1

    async def test_session_contains_user_data(self, auth_service):
        _, state = await auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="valid_code", state=state)
        session = auth_service._session_store.sessions[session_id]
        assert session["user"]["login"] == "testuser"
        assert session["user"]["id"] == 12345

    async def test_missing_code_raises(self, auth_service):
        _, state = await auth_service.create_login_url()
        with pytest.raises(OAuthError, match="Missing authorization code"):
            await auth_service.handle_callback(code="", state=state)

    async def test_invalid_state_raises(self, auth_service):
        with pytest.raises(OAuthError, match="Invalid or expired"):
            await auth_service.handle_callback(code="valid_code", state="bad_state")

    async def test_raises_when_oauth_not_configured(self, auth_service_no_oauth):
        with pytest.raises(OAuthNotConfiguredError):
            await auth_service_no_oauth.handle_callback(code="code", state="state")

    async def test_callback_fails_when_session_storage_unconfigured(self, auth_service):
        from app.services.session_store import SessionStore
        _, state = await auth_service.create_login_url()
        auth_service._session_store = SessionStore(redis_url="", redis_token="", encryption_key="")
        with pytest.raises(OAuthError, match="Failed to persist session|Internal error|Failed to validate"):
            await auth_service.handle_callback(code="valid_code", state=state)

    async def test_callback_fails_when_session_storage_has_invalid_key(self, auth_service):
        from app.services.session_store import SessionStore
        _, state = await auth_service.create_login_url()
        auth_service._session_store = SessionStore(
            redis_url="https://redis.example.com", redis_token="tok", encryption_key="invalid-key"
        )
        with pytest.raises(OAuthError, match="Failed to persist session|Internal error|Failed to validate"):
            await auth_service.handle_callback(code="valid_code", state=state)


class TestGetCurrentUser:
    """Tests for AuthService.get_current_user."""

    async def test_returns_user_for_valid_session(self, auth_service):
        _, state = await auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="code", state=state)
        user = await auth_service.get_current_user(session_id)
        assert user["login"] == "testuser"

    async def test_raises_for_missing_session_id(self, auth_service):
        with pytest.raises(AuthenticationError):
            await auth_service.get_current_user(None)

    async def test_raises_for_invalid_session_id(self, auth_service):
        with pytest.raises(AuthenticationError):
            await auth_service.get_current_user("nonexistent_session")


class TestLogout:
    """Tests for AuthService.logout."""

    async def test_logout_removes_session(self, auth_service):
        _, state = await auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="code", state=state)
        assert len(auth_service._session_store.sessions) == 1
        await auth_service.logout(session_id)
        assert len(auth_service._session_store.sessions) == 0

    async def test_logout_with_no_session_is_safe(self, auth_service):
        # Should not raise
        await auth_service.logout(None)
        await auth_service.logout("nonexistent")

    async def test_user_not_found_after_logout(self, auth_service):
        _, state = await auth_service.create_login_url()
        session_id = await auth_service.handle_callback(code="code", state=state)
        await auth_service.logout(session_id)
        with pytest.raises(AuthenticationError):
            await auth_service.get_current_user(session_id)
