export default function EmptyState({ onAnalyzeAnother }) {
  return (
    <section className="px-5 pb-16" id="empty-state">
      <div className="mx-auto max-w-md">
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-10 text-center animate-scale-in">
          {/* Animated checkmark */}
          <div className="relative mx-auto mb-6 inline-flex items-center justify-center">
            {/* Pulsing ring */}
            <div className="absolute h-24 w-24 rounded-full border-2 border-[rgba(34,197,94,0.15)] animate-pulse-soft" />
            <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-[rgba(34,197,94,0.25)] bg-[var(--color-green-bg)]">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" className="text-[var(--color-green)]">
                <path
                  d="M20 6L9 17L4 12"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray="24"
                  className="animate-check-draw"
                />
              </svg>
            </div>
          </div>

          <h2 className="mb-2 text-xl font-bold text-[var(--color-text-primary)]">
            ✅ No conflicting pull requests detected.
          </h2>
          <p className="mx-auto mb-8 max-w-xs text-sm leading-relaxed text-[var(--color-text-secondary)]">
            Your PR appears safe to merge based on file overlap.
          </p>

          <button
            onClick={onAnalyzeAnother}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[var(--color-blue)] to-[var(--color-purple)] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_0_20px_rgba(59,130,246,0.2)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_0_30px_rgba(59,130,246,0.35)]"
            id="analyze-another-btn"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 102.13-9.36L1 10" />
            </svg>
            Analyze Another Pull Request
          </button>
        </div>
      </div>
    </section>
  );
}
