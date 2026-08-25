"""
Authentication endpoints — GitHub OAuth flow.

GET  /auth/github/login     → Redirect to GitHub OAuth authorization.
GET  /auth/github/callback  → Handle OAuth callback, create session.
GET  /auth/me               → Return current authenticated user.
POST /auth/logout            → Clear the user's session.
"""

import logging

from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import RedirectResponse

from app.api.dependencies import get_auth_service
from app.core.constants import OAUTH_STATE_COOKIE_NAME, SESSION_COOKIE_NAME
from app.exceptions.auth import OAuthError
from app.schemas.auth import AuthUser, AuthUserResponse, LogoutResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get(
    "/github/login",
    summary="Start GitHub OAuth login",
    description="Redirects the user to GitHub's OAuth authorization page.",
    responses={
        307: {"description": "Redirect to GitHub OAuth"},
        503: {"description": "OAuth not configured"},
    },
)
async def github_login(
    service: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    """
    Generate a GitHub OAuth authorization URL and redirect the user.

    Sets the OAuth state parameter in an HTTP-only cookie for CSRF validation
    when the callback is received.
    """
    authorization_url, state = service.create_login_url()

    response = RedirectResponse(url=authorization_url, status_code=307)
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=state,
        max_age=600,  # 10 minutes
        httponly=True,
        samesite="lax",
        secure=False,  # False for localhost; True in production
        path="/",
    )
    return response


@router.get(
    "/github/callback",
    summary="GitHub OAuth callback",
    description="Handles the OAuth callback from GitHub, exchanges the code for a session.",
    responses={
        307: {"description": "Redirect to frontend after successful auth"},
        400: {"description": "Invalid OAuth callback parameters"},
    },
)
async def github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    service: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    """
    Handle the GitHub OAuth callback.

    Validates the state parameter, exchanges the authorization code for
    an access token, fetches the user profile, creates a session, and
    redirects back to the frontend.
    """
    # Check for OAuth error from GitHub
    error = request.query_params.get("error")
    if error:
        error_desc = request.query_params.get("error_description", error)
        logger.warning("GitHub OAuth error: %s", error_desc)
        raise OAuthError(f"GitHub denied access: {error_desc}")

    if not code:
        raise OAuthError("Missing authorization code from GitHub.")

    if not state:
        raise OAuthError("Missing state parameter from GitHub.")

    # Retrieve the state from the cookie for validation
    cookie_state = request.cookies.get(OAUTH_STATE_COOKIE_NAME)
    if not cookie_state:
        raise OAuthError("Missing OAuth state cookie. Please try again.")

    if state != cookie_state:
        raise OAuthError("OAuth state mismatch. Possible CSRF attack.")

    # Delegate to service: validate state, exchange code, create session
    session_id = await service.handle_callback(code=code, state=state)

    # Build the redirect URL back to the frontend
    from app.core.config import get_settings
    settings = get_settings()
    redirect_url = settings.FRONTEND_URL

    response = RedirectResponse(url=redirect_url, status_code=307)

    # Set the session cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,  # False for localhost; True in production
        path="/",
    )

    # Clear the OAuth state cookie (no longer needed)
    response.delete_cookie(key=OAUTH_STATE_COOKIE_NAME, path="/")

    return response


@router.get(
    "/me",
    response_model=AuthUserResponse,
    summary="Get current user",
    description="Returns the currently authenticated user's information.",
    responses={
        401: {"description": "Not authenticated"},
    },
)
async def get_me(
    service: AuthService = Depends(get_auth_service),
    prinsight_session: str | None = Cookie(default=None),
) -> AuthUserResponse:
    """
    Return the currently authenticated user's GitHub profile.

    The session ID is read from the HTTP-only cookie set during login.
    Returns 401 if the user is not authenticated.
    """
    user_data = service.get_current_user(prinsight_session)
    return AuthUserResponse(data=AuthUser(**user_data))


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Log out",
    description="Clears the user's session and removes the session cookie.",
)
async def logout(
    response: Response,
    service: AuthService = Depends(get_auth_service),
    prinsight_session: str | None = Cookie(default=None),
) -> LogoutResponse:
    """
    Log out the current user.

    Removes the server-side session and clears the session cookie.
    """
    service.logout(prinsight_session)

    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return LogoutResponse()
