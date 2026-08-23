import { useState, useEffect, useCallback } from 'react';
import { fetchCurrentUser, logout as logoutApi, getLoginUrl } from '../services/auth';

/**
 * Custom hook for authentication state management.
 *
 * On mount, checks for an existing session by calling /api/v1/auth/me.
 * Provides login/logout functions and the current user state.
 *
 * Usage:
 *   const { user, loading, login, logout } = useAuth();
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    let cancelled = false;

    async function checkAuth() {
      const userData = await fetchCurrentUser();
      if (!cancelled) {
        setUser(userData);
        setLoading(false);
      }
    }

    checkAuth();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(() => {
    // Full page redirect to the backend OAuth login endpoint.
    // The backend redirects to GitHub, which redirects back to the callback,
    // which redirects back to the frontend.
    window.location.href = getLoginUrl();
  }, []);

  const logout = useCallback(async () => {
    await logoutApi();
    setUser(null);
  }, []);

  return { user, loading, login, logout };
}
