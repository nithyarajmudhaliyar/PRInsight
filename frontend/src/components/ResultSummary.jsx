import RiskBadge from './RiskBadge';

/**
 * Summary header shown at the top of the results page.
 *
 * Displays: Repository, PR Number, Title, Author, Files Changed,
 * PRs Checked, Conflicts Found, Risk Badge, and Analysis Metadata.
 *
 * Data shape comes from the normalizeResponse adapter in api.js:
 *   { repository, pullRequest, openPRsChecked, conflictsFound, overallRisk, metadata }
 */
export default function ResultSummary({ data }) {
  const { repository, pullRequest, openPRsChecked, conflictsFound, overallRisk, metadata } = data;

  const stats = [
    { label: 'Repository', value: repository, icon: 'folder' },
    { label: 'PR Number', value: `#${pullRequest.number}`, icon: 'pr' },
    { label: 'Title', value: pullRequest.title, icon: 'branch' },
    { label: 'Author', value: pullRequest.author, icon: 'user' },
    { label: 'Files Changed', value: pullRequest.filesChanged, icon: 'file' },
    { label: 'PRs Checked', value: openPRsChecked, icon: 'check' },
  ];

  return (
    <section className="px-5 pb-8 pt-28 animate-fade-in" id="result-summary">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-6">
          <div className="mb-1 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">Analysis Results</h1>
            <RiskBadge risk={overallRisk} size="lg" />
          </div>
          <p className="text-sm text-[var(--color-text-secondary)]">{pullRequest.title}</p>
        </div>

        {/* Stats grid */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {stats.map((s, i) => (
            <div
              key={s.label}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4 transition-all duration-200 hover:border-[var(--color-border-hover)] hover:bg-[var(--color-bg-card-hover)] animate-fade-in-up"
              style={{ animationDelay: `${i * 0.04}s`, opacity: 0 }}
              id={`stat-${s.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
                {s.label}
              </div>
              <div className="truncate text-sm font-semibold text-[var(--color-text-primary)]" title={String(s.value)}>
                {s.value}
              </div>
            </div>
          ))}
        </div>

        {/* Conflicts bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="bg-gradient-to-r from-[var(--color-blue)] to-[var(--color-purple)] bg-clip-text text-3xl font-extrabold text-transparent">
              {conflictsFound}
            </span>
            <span className="text-sm font-medium text-[var(--color-text-secondary)]">
              Potential {conflictsFound === 1 ? 'Conflict' : 'Conflicts'} Found
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-[var(--color-text-muted)]">
            <span>{pullRequest.filesChanged} files analyzed</span>
          </div>
        </div>

        {/* Analysis Metadata */}
        {metadata && (
          <div
            className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] px-6 py-3 text-xs text-[var(--color-text-muted)] animate-fade-in-up"
            style={{ animationDelay: '0.3s', opacity: 0 }}
            id="analysis-metadata"
          >
            {/* Analysis Duration */}
            <span className="inline-flex items-center gap-1.5">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              {metadata.analysisDurationMs >= 1000
                ? `${(metadata.analysisDurationMs / 1000).toFixed(1)} s`
                : `${Math.max(1, Math.round(metadata.analysisDurationMs))} ms`
              }
            </span>

            {/* Cache Status Badge */}
            {metadata.cacheHit ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[rgba(249,115,22,0.2)] bg-[var(--color-orange-bg)] px-2.5 py-0.5 text-[11px] font-semibold text-[var(--color-orange)]">
                ⚡ Cache Hit
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[rgba(34,197,94,0.2)] bg-[var(--color-green-bg)] px-2.5 py-0.5 text-[11px] font-semibold text-[var(--color-green)]">
                🟢 Fresh Analysis
              </span>
            )}

            {/* PRs Analyzed */}
            <span className="inline-flex items-center gap-1.5">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4-4v-2" /><circle cx="8.5" cy="7" r="4" /><line x1="20" y1="8" x2="20" y2="14" /><line x1="23" y1="11" x2="17" y2="11" />
              </svg>
              {openPRsChecked} PRs checked
            </span>

          </div>
        )}

        {/* Repository Warning — shown as a standalone card only when present */}
        {metadata?.warning && (
          <div
            className="mt-3 flex items-start gap-3 rounded-xl border border-[rgba(249,115,22,0.2)] bg-[var(--color-orange-bg)] px-5 py-3.5 animate-fade-in-up"
            style={{ animationDelay: '0.35s', opacity: 0 }}
            id="analysis-warning"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0 text-[var(--color-orange)]">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span className="text-xs leading-relaxed text-[var(--color-orange)]">
              {metadata.warning}
            </span>
          </div>
        )}
      </div>
    </section>
  );
}
