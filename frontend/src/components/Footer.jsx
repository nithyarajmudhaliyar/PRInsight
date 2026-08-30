export default function Footer() {
  return (
    <footer className="mt-auto border-t border-[var(--color-border)] px-5 py-8">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-3 text-center">
        <div className="flex items-center gap-2">
          <img src="/logo.svg" alt="PRInsight logo" width="18" height="18" className="shrink-0" />
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
