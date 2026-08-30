import LoginButton from './LoginButton';
import UserMenu from './UserMenu';

export default function Navbar({ user, onLogin, onLogout }) {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-bg-primary)]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-5">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2 transition-opacity hover:opacity-80" id="nav-logo">
          <img src="/logo.svg" alt="PRInsight logo" width="28" height="28" className="shrink-0" />
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
