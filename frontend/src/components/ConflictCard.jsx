import RiskBadge from './RiskBadge';

/**
 * Card displaying a single conflicting Pull Request.
 *
 * Backend conflict shape (after normalization in api.js):
 *   { id, number, title, author (string), risk, overlappingFiles, overlapCount, url }
 *
 * Changes from mock format:
 *   - author is now a plain string (was { name, avatar })
 *   - no more branch or reason fields
 *   - PR number is clickable and opens GitHub
 */
export default function ConflictCard({ conflict, index }) {
  const { number, title, author, risk, overlappingFiles, overlapCount, url } = conflict;

  // Generate initials from the author login for the avatar
  const initials = author
    ? author.slice(0, 2).toUpperCase()
    : '??';

  return (
    <div
      className="group relative overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 transition-all duration-300 hover:-translate-y-0.5 hover:border-[var(--color-border-hover)] hover:shadow-[0_8px_32px_rgba(0,0,0,0.45)] animate-fade-in-up"
      style={{ animationDelay: `${0.08 + index * 0.06}s`, opacity: 0 }}
      id={`conflict-card-${number}`}
    >
      {/* Hover glow overlay */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[var(--color-blue-glow)] to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

      {/* Header */}
      <div className="relative z-10 mb-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          {/* Avatar */}
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--color-blue)] to-[var(--color-purple)] text-[10px] font-bold text-white">
            {initials}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {/* PR number — clickable, opens GitHub in new tab */}
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-semibold text-[var(--color-blue)] hover:underline"
              >
                #{number}
              </a>
              <h3 className="truncate text-sm font-semibold text-[var(--color-text-primary)]">{title}</h3>
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-[var(--color-text-secondary)]">
              <span>{author}</span>
              {overlapCount && (
                <span className="inline-flex items-center gap-1 rounded bg-[var(--color-bg-elevated)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-text-muted)]">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  {overlapCount} {overlapCount === 1 ? 'file' : 'files'}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <RiskBadge risk={risk} />
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {overlapCount} overlapping {overlapCount === 1 ? 'file' : 'files'}
          </span>
        </div>
      </div>

      {/* Overlapping Files */}
      <div className="relative z-10 mb-4">
        <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          Overlapping Files
        </div>
        <div className="flex flex-wrap gap-1.5">
          {overlappingFiles.map((file) => (
            <code
              key={file}
              className="rounded border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-2 py-0.5 font-mono text-[11px] text-[var(--color-text-secondary)] transition-colors group-hover:border-[var(--color-border-hover)]"
            >
              {file}
            </code>
          ))}
        </div>
      </div>

      {/* Action */}
      <div className="relative z-10">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-[11px] font-medium text-[var(--color-text-secondary)] transition-all duration-200 hover:border-[var(--color-blue)] hover:bg-[var(--color-blue-glow)] hover:text-[var(--color-blue)]"
          id={`view-pr-${number}`}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
          View Pull Request
        </a>
      </div>
    </div>
  );
}
