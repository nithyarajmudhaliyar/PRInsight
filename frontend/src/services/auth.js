/**
 * PRInsight Auth service — communicates with the FastAPI auth endpoints.
 *
 * @module services/auth
 */

const API_BASE_URL = 'http://localhost:8000';

/**
 * Get the GitHub OAuth login URL.
 *
 * This returns the URL that the browser should navigate to (full redirect).
 * The backend will redirect the user to GitHub's OAuth page.
 *
 * @returns {string} The backend OAuth login endpoint URL
 */
export function getLoginUrl() {
  return `${API_BASE_URL}/api/v1/auth/github/login`;
}

/**
 * Fetch the currently authenticated user.
 *
 * Calls GET /api/v1/auth/me with credentials (cookies) included.
 * Returns the user object if authenticated, or null if not.
 *
 * @returns {Promise<object|null>} User data or null
 */
export async function fetchCurrentUser() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      credentials: 'include',
    });

    if (response.status === 401) {
      return null;
    }

    if (!response.ok) {
      return null;
    }

    const json = await response.json();
    return json.data;
  } catch {
    // Network error — backend unreachable, treat as unauthenticated
    return null;
  }
}

/**
 * Log out the current user.
 *
 * Calls POST /api/v1/auth/logout with credentials (cookies) included.
 * The backend will clear the session cookie.
 *
 * @returns {Promise<boolean>} true if logout succeeded
 */
export async function logout() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    return response.ok;
  } catch {
    return false;
  }
}
