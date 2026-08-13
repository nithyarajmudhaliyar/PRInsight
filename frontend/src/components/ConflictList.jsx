import ConflictCard from './ConflictCard';

export default function ConflictList({ conflicts }) {
  return (
    <section className="px-5 pb-12" id="conflict-list">
      <div className="mx-auto max-w-4xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-bold text-[var(--color-text-primary)]">Conflicting Pull Requests</h2>
          <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3 py-0.5 text-xs font-medium text-[var(--color-text-muted)]">
            {conflicts.length} found
          </span>
        </div>
        <div className="flex flex-col gap-3">
          {conflicts.map((conflict, i) => (
            <ConflictCard key={conflict.id} conflict={conflict} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
