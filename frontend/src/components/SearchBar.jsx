import { useState, useMemo } from 'react';
import { parseGitHubPRUrl } from '../utils/helpers';

export default function SearchBar({ onAnalyze, disabled }) {
  const [url, setUrl] = useState('');

  const parsed = useMemo(() => parseGitHubPRUrl(url), [url]);
  const isValid = parsed !== null;
  const showPreview = url.length > 15;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (isValid && !disabled) onAnalyze(parsed);
  };

  return (
    <section className="relative z-10 px-5 pb-10" id="search-section">
      <div className="mx-auto max-w-2xl">
        {/* Input */}
        <form onSubmit={handleSubmit} id="search-form">
          <div
            className={`flex items-center gap-2 rounded-2xl border bg-[var(--color-bg-card)] p-1.5 pl-5 shadow-lg transition-all duration-300
              ${isValid
                ? 'border-[var(--color-green)]/40 shadow-[0_0_24px_rgba(34,197,94,0.1)]'
                : url.length > 15
                  ? 'border-[var(--color-red)]/30 shadow-[0_0_24px_rgba(239,68,68,0.06)]'
                  : 'border-[var(--color-border)] hover:border-[var(--color-border-hover)]'
              }`}
          >
            {/* Icon */}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-[var(--color-text-muted)]">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>

            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repository/pull/123"
              className="min-w-0 flex-1 bg-transparent py-3 text-sm text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)]"
              id="search-input"
              aria-label="Pull Request URL"
              spellCheck={false}
              autoComplete="off"
            />

            <button
              type="submit"
              disabled={!isValid || disabled}
              className="flex shrink-0 items-center gap-2 rounded-xl bg-gradient-to-r from-[var(--color-blue)] to-[var(--color-purple)] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_0_20px_rgba(59,130,246,0.2)] transition-all duration-200 hover:shadow-[0_0_30px_rgba(59,130,246,0.35)] hover:scale-[1.02] active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none disabled:hover:scale-100"
              id="analyze-btn"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="13 17 18 12 13 7" />
                <polyline points="6 17 11 12 6 7" />
              </svg>
              Analyze
            </button>
          </div>
        </form>

        {/* Preview Card */}
        {showPreview && (
          <div className={`mt-4 overflow-hidden rounded-xl border bg-[var(--color-bg-card)] transition-all duration-300 animate-fade-in
            ${isValid ? 'border-[var(--color-green)]/20' : 'border-[var(--color-red)]/20'}`}>
            <div className="flex items-center gap-6 px-5 py-4">
              {isValid ? (
                <>
                  <PreviewItem label="Repository" value={`${parsed.owner}/${parsed.repo}`} />
                  <Divider />
                  <PreviewItem label="Pull Request" value={`#${parsed.prNumber}`} />
                  <Divider />
                  <PreviewItem
                    label="Status"
                    value="Ready for Analysis"
                    valueClass="text-[var(--color-green)]"
                  />
                </>
              ) : (
                <div className="flex items-center gap-2 text-xs text-[var(--color-red)]">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="15" y1="9" x2="9" y2="15" />
                    <line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                  Invalid GitHub Pull Request URL. Expected format: https://github.com/owner/repo/pull/123
                </div>
              )}
            </div>
          </div>
        )}

        <p className="mt-3 text-center text-[11px] text-[var(--color-text-muted)]">
          Paste a GitHub Pull Request URL to scan for potential conflicts
        </p>
      </div>
    </section>
  );
}

function PreviewItem({ label, value, valueClass = 'text-[var(--color-text-primary)]' }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">{label}</div>
      <div className={`mt-0.5 truncate text-sm font-semibold ${valueClass}`}>{value}</div>
    </div>
  );
}

function Divider() {
  return <div className="h-8 w-px shrink-0 bg-[var(--color-border)]" />;
}
