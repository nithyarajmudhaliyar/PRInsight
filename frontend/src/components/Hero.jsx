export default function Hero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-8 text-center" id="hero-section">
      {/* Background orbs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div className="absolute -top-24 -right-24 h-[420px] w-[420px] rounded-full bg-[var(--color-blue)] opacity-[0.08] blur-[100px] animate-float" />
        <div className="absolute -bottom-16 -left-16 h-[350px] w-[350px] rounded-full bg-[var(--color-purple)] opacity-[0.06] blur-[100px] animate-float [animation-delay:-3s]" />
        {/* Grid */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)',
            backgroundSize: '56px 56px',
            maskImage: 'radial-gradient(ellipse at center, black 20%, transparent 70%)',
            WebkitMaskImage: 'radial-gradient(ellipse at center, black 20%, transparent 70%)',
          }}
        />
      </div>

      <div className="relative z-10 mx-auto max-w-2xl px-5 animate-fade-in">
        {/* Badge */}
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3 py-1 text-[11px] font-medium uppercase tracking-widest text-[var(--color-text-secondary)]">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-green)] animate-pulse-soft" />
          Developer Tool
        </div>

        <h1 className="text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl">
          Know Your Merge Risk{' '}
          <br className="hidden sm:block" />
          <span className="bg-gradient-to-r from-[var(--color-blue)] to-[var(--color-purple)] bg-clip-text text-transparent">
            Before You Click Merge.
          </span>
        </h1>

        <p className="mx-auto mt-5 max-w-lg text-base leading-relaxed text-[var(--color-text-secondary)] sm:text-lg">
          Analyze a GitHub Pull Request and detect overlapping changes before merge conflicts happen.
        </p>
      </div>
    </section>
  );
}
