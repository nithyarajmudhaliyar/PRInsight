import { useState, useRef, useEffect } from 'react';

/**
 * Authenticated user menu displayed in the Navbar.
 *
 * Shows the user's GitHub avatar and username with a dropdown
 * containing a logout option. Styled with existing design tokens.
 */
export default function UserMenu({ user, onLogout }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-2 py-1 text-xs font-medium text-[var(--color-text-secondary)] transition-all hover:border-[var(--color-border-hover)] hover:text-[var(--color-text-primary)] cursor-pointer"
        id="user-menu-btn"
      >
        {user.avatar_url ? (
          <img
            src={user.avatar_url}
            alt={user.login}
            className="h-5 w-5 rounded-full"
          />
        ) : (
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--color-blue)] text-[10px] font-bold text-white">
            {user.login?.[0]?.toUpperCase() || '?'}
          </div>
        )}
        <span className="max-w-[100px] truncate">{user.login}</span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 mt-2 w-44 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] py-1 shadow-lg animate-scale-in z-50">
          <div className="border-b border-[var(--color-border)] px-3 py-2">
            <p className="text-xs font-medium text-[var(--color-text-primary)] truncate">
              {user.name || user.login}
            </p>
            <p className="text-[10px] text-[var(--color-text-muted)] truncate">
              @{user.login}
            </p>
          </div>
          <button
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-xs text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-card-hover)] hover:text-[var(--color-red)] cursor-pointer"
            id="logout-btn"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
              <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
