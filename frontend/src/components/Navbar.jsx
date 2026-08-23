import LoginButton from './LoginButton';
import UserMenu from './UserMenu';

export default function Navbar({ user, onLogin, onLogout }) {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-bg-primary)]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-5">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2 transition-opacity hover:opacity-80" id="nav-logo">
          <svg width="24" height="24" viewBox="0 0 32 32" fill="none" className="shrink-0">
            <defs>
              <linearGradient id="navGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#3B82F6" />
                <stop offset="100%" stopColor="#8B5CF6" />
              </linearGradient>
            </defs>
            <rect width="32" height="32" rx="8" fill="url(#navGrad)" />
            <path d="M10 16 L14 20 L22 12" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
          <span className="text-base font-bold tracking-tight text-[var(--color-text-primary)]">
            PR<span className="bg-gradient-to-r from-[var(--color-blue)] to-[var(--color-purple)] bg-clip-text text-transparent">Insight</span>
          </span>
        </a>

        {/* Right Actions */}
        <div className="flex items-center gap-2">
          {user ? (
            <UserMenu user={user} onLogout={onLogout} />
          ) : (
            <LoginButton onLogin={onLogin} />
          )}
        </div>
      </div>
    </nav>
  );
}
