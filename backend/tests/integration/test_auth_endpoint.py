"""
Integration tests for the authentication endpoints.

Tests the full HTTP request → response flow for:
    GET  /api/v1/auth/github/login
    GET  /api/v1/auth/github/callback
    GET  /api/v1/auth/me
    POST /api/v1/auth/logout
"""

from unittest.mock import AsyncMock, patch

from app.api.dependencies import get_auth_service
from app.services.auth_service import AuthService


class TestGitHubLoginEndpoint:
    """Tests for GET /api/v1/auth/github/login."""

    def test_login_redirects_to_github(self, test_client):
        """Login endpoint should redirect to GitHub OAuth authorization URL."""
        mock_service = AsyncMock(spec=AuthService)
        mock_service.create_login_url.return_value = (
            "https://github.com/login/oauth/authorize?client_id=test&state=abc123",
            "abc123",
        )
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.get(
                "/api/v1/auth/github/login",
                follow_redirects=False,
            )
            assert response.status_code == 307
            assert "github.com/login/oauth/authorize" in response.headers["location"]
            # Should set the OAuth state cookie
            cookies = response.headers.get_list("set-cookie")
            state_cookie = [c for c in cookies if "prinsight_oauth_state" in c]
            assert len(state_cookie) == 1
        finally:
            test_client.app.dependency_overrides.clear()

    def test_login_returns_503_when_oauth_not_configured(self, test_client):
        """Login should return 503 when OAuth credentials are missing."""
        from app.exceptions.auth import OAuthNotConfiguredError

        mock_service = AsyncMock(spec=AuthService)
        mock_service.create_login_url.side_effect = OAuthNotConfiguredError()
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.get(
                "/api/v1/auth/github/login",
                follow_redirects=False,
            )
            assert response.status_code == 503
            data = response.json()
            assert data["error"]["code"] == "OAUTH_NOT_CONFIGURED"
        finally:
            test_client.app.dependency_overrides.clear()


class TestGitHubCallbackEndpoint:
    """Tests for GET /api/v1/auth/github/callback."""

    def test_callback_missing_code_returns_400(self, test_client):
        """Callback without a code parameter should return 400."""
        mock_service = AsyncMock(spec=AuthService)
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.get(
                "/api/v1/auth/github/callback",
                follow_redirects=False,
            )
            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == "OAUTH_ERROR"
        finally:
            test_client.app.dependency_overrides.clear()

    def test_callback_missing_state_cookie_returns_400(self, test_client):
        """Callback without the state cookie should return 400."""
        mock_service = AsyncMock(spec=AuthService)
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.get(
                "/api/v1/auth/github/callback?code=testcode&state=teststate",
                follow_redirects=False,
            )
            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == "OAUTH_ERROR"
            assert "state cookie" in data["error"]["message"].lower()
        finally:
            test_client.app.dependency_overrides.clear()

    def test_callback_state_mismatch_returns_400(self, test_client):
        """Callback with mismatched state should return 400."""
        mock_service = AsyncMock(spec=AuthService)
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.get(
                "/api/v1/auth/github/callback?code=testcode&state=wrongstate",
                cookies={"prinsight_oauth_state": "correctstate"},
                follow_redirects=False,
            )
            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == "OAUTH_ERROR"
        finally:
            test_client.app.dependency_overrides.clear()

    def test_callback_github_error_returns_400(self, test_client):
        """Callback with GitHub error parameter should return 400."""
        mock_service = AsyncMock(spec=AuthService)
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.get(
                "/api/v1/auth/github/callback?error=access_denied&error_description=User+denied+access",
                follow_redirects=False,
            )
            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == "OAUTH_ERROR"
        finally:
            test_client.app.dependency_overrides.clear()

    def test_successful_callback_redirects_and_sets_cookie(self, test_client):
        """Successful callback should redirect to frontend and set session cookie."""
        mock_service = AsyncMock(spec=AuthService)
        mock_service.handle_callback.return_value = "test_session_id_123"
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.get(
                "/api/v1/auth/github/callback?code=valid_code&state=valid_state",
                cookies={"prinsight_oauth_state": "valid_state"},
                follow_redirects=False,
            )
            assert response.status_code == 307
            assert "localhost:5173" in response.headers["location"]
            # Should set the session cookie
            cookies = response.headers.get_list("set-cookie")
            session_cookie = [c for c in cookies if "prinsight_session" in c]
            assert len(session_cookie) >= 1
        finally:
            test_client.app.dependency_overrides.clear()


class TestMeEndpoint:
    """Tests for GET /api/v1/auth/me."""

    def test_me_returns_401_when_unauthenticated(self, test_client):
        """Should return 401 when no session cookie is present."""
        response = test_client.get("/api/v1/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert data["status"] == "error"
        assert data["error"]["code"] == "AUTH_ERROR"

    def test_me_returns_user_when_authenticated(self, test_client):
        """Should return user data when a valid session exists."""
        mock_service = AsyncMock(spec=AuthService)
        mock_service.get_current_user.return_value = {
            "id": 12345,
            "login": "testuser",
            "name": "Test User",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
        }
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.get(
                "/api/v1/auth/me",
                cookies={"prinsight_session": "valid_session_id"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["data"]["login"] == "testuser"
            assert data["data"]["id"] == 12345
        finally:
            test_client.app.dependency_overrides.clear()

    def test_me_returns_401_for_invalid_session(self, test_client):
        """Should return 401 when session ID is invalid."""
        from app.exceptions.auth import AuthenticationError

        mock_service = AsyncMock(spec=AuthService)
        mock_service.get_current_user.side_effect = AuthenticationError()
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.get(
                "/api/v1/auth/me",
                cookies={"prinsight_session": "invalid_session_id"},
            )
            assert response.status_code == 401
        finally:
            test_client.app.dependency_overrides.clear()


class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_clears_session(self, test_client):
        """Logout should return success and clear the session cookie."""
        mock_service = AsyncMock(spec=AuthService)
        mock_service.logout.return_value = None
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.post(
                "/api/v1/auth/logout",
                cookies={"prinsight_session": "some_session_id"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            # Session cookie should be cleared
            cookies = response.headers.get_list("set-cookie")
            cleared = [c for c in cookies if "prinsight_session" in c]
            assert len(cleared) >= 1
        finally:
            test_client.app.dependency_overrides.clear()

    def test_logout_without_session_succeeds(self, test_client):
        """Logout without a session cookie should still succeed gracefully."""
        mock_service = AsyncMock(spec=AuthService)
        mock_service.logout.return_value = None
        test_client.app.dependency_overrides[get_auth_service] = lambda: mock_service

        try:
            response = test_client.post("/api/v1/auth/logout")
            assert response.status_code == 200
        finally:
            test_client.app.dependency_overrides.clear()


class TestAuthErrorFormat:
    """Verify auth errors follow the consistent error response envelope."""

    def test_auth_error_has_consistent_envelope(self, test_client):
        """Auth error responses must have status, error.code, error.message."""
        response = test_client.get("/api/v1/auth/me")
        data = response.json()

        assert "status" in data
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
