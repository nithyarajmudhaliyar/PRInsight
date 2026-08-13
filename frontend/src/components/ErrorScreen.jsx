/**
 * Full-screen error display with retry capability.
 *
 * Shown when the backend returns an error (400, 404, 422, 429, 500)
 * or when the network is unreachable. The error message comes from
 * the api.js error handler — already user-friendly.
 */
export default function ErrorScreen({ message, onRetry }) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center px-5 animate-fade-in" id="error-screen">
      <div className="mx-auto max-w-md text-center">
        {/* Error icon */}
        <div className="relative mx-auto mb-6 inline-flex items-center justify-center">
          <div className="absolute h-24 w-24 rounded-full border-2 border-[rgba(239,68,68,0.15)] animate-pulse-soft" />
          <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-[rgba(239,68,68,0.25)] bg-[var(--color-red-bg)]">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" className="text-[var(--color-red)]">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
              <line x1="15" y1="9" x2="9" y2="15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <line x1="9" y1="9" x2="15" y2="15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>
        </div>

        <h2 className="mb-2 text-xl font-bold text-[var(--color-text-primary)]">
          Analysis Failed
        </h2>
        <p className="mx-auto mb-8 max-w-xs text-sm leading-relaxed text-[var(--color-text-secondary)]">
          {message || 'Something went wrong. Please try again.'}
        </p>

        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[var(--color-blue)] to-[var(--color-purple)] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_0_20px_rgba(59,130,246,0.2)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_0_30px_rgba(59,130,246,0.35)]"
          id="retry-btn"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="1 4 1 10 7 10" />
            <path d="M3.51 15a9 9 0 102.13-9.36L1 10" />
          </svg>
          Try Again
        </button>
      </div>
    </div>
  );
}
