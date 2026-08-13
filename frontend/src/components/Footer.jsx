export default function Footer() {
  return (
    <footer className="mt-auto border-t border-[var(--color-border)] px-5 py-8">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-3 text-center">
        <div className="flex items-center gap-2">
          <svg width="18" height="18" viewBox="0 0 32 32" fill="none" className="shrink-0">
            <defs>
              <linearGradient id="fGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#3B82F6" />
                <stop offset="100%" stopColor="#8B5CF6" />
              </linearGradient>
            </defs>
            <rect width="32" height="32" rx="8" fill="url(#fGrad)" />
            <path d="M10 16 L14 20 L22 12" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
          <span className="text-sm font-bold text-[var(--color-text-primary)]">
            PR<span className="bg-gradient-to-r from-[var(--color-blue)] to-[var(--color-purple)] bg-clip-text text-transparent">Insight</span>
          </span>
        </div>
        <p className="text-xs text-[var(--color-text-muted)]">
          Analyze. Compare. Merge With Confidence.
        </p>
      </div>
    </footer>
  );
}
