const features = [
  {
    title: 'Detect Potential Conflicts',
    description: 'Scan all open PRs and find file-level overlaps that could cause merge issues.',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    ),
  },
  {
    title: 'Fast Repository Analysis',
    description: 'Quickly compare changed files across every active Pull Request in the repo.',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
  {
    title: 'Merge With Confidence',
    description: 'Get a clear risk assessment so you can merge knowing nothing will break.',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
];

export default function FeatureCards() {
  return (
    <section className="px-5 pb-20" id="features-section">
      <div className="mx-auto grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-3">
        {features.map((f, i) => (
          <div
            key={f.title}
            className="group relative overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6 text-center transition-all duration-300 hover:-translate-y-1 hover:border-[var(--color-border-hover)] hover:shadow-[0_8px_32px_rgba(0,0,0,0.4)] animate-fade-in-up"
            style={{ animationDelay: `${0.15 + i * 0.1}s`, opacity: 0 }}
            id={`feature-card-${i}`}
          >
            {/* Hover glow */}
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[var(--color-blue-glow)] to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

            <div className="relative z-10">
              <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-lg border border-[rgba(59,130,246,0.15)] bg-[var(--color-blue-glow)] text-[var(--color-blue)] transition-all duration-300 group-hover:shadow-[0_0_20px_rgba(59,130,246,0.2)]">
                {f.icon}
              </div>
              <h3 className="mb-1.5 text-sm font-semibold text-[var(--color-text-primary)]">{f.title}</h3>
              <p className="text-xs leading-relaxed text-[var(--color-text-secondary)]">{f.description}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
