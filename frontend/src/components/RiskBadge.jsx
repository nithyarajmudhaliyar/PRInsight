const config = {
  High:           { bg: 'bg-[var(--color-red-bg)]', text: 'text-[var(--color-red)]',    border: 'border-[rgba(239,68,68,0.2)]',  dot: 'bg-[var(--color-red)]   shadow-[0_0_6px_rgba(239,68,68,0.5)]' },
  'High Risk':    { bg: 'bg-[var(--color-red-bg)]', text: 'text-[var(--color-red)]',    border: 'border-[rgba(239,68,68,0.2)]',  dot: 'bg-[var(--color-red)]   shadow-[0_0_6px_rgba(239,68,68,0.5)]' },
  Medium:         { bg: 'bg-[var(--color-orange-bg)]', text: 'text-[var(--color-orange)]', border: 'border-[rgba(249,115,22,0.2)]', dot: 'bg-[var(--color-orange)] shadow-[0_0_6px_rgba(249,115,22,0.5)]' },
  'Medium Risk':  { bg: 'bg-[var(--color-orange-bg)]', text: 'text-[var(--color-orange)]', border: 'border-[rgba(249,115,22,0.2)]', dot: 'bg-[var(--color-orange)] shadow-[0_0_6px_rgba(249,115,22,0.5)]' },
  Low:            { bg: 'bg-[var(--color-yellow-bg)]', text: 'text-[var(--color-yellow)]', border: 'border-[rgba(234,179,8,0.2)]',  dot: 'bg-[var(--color-yellow)] shadow-[0_0_6px_rgba(234,179,8,0.5)]' },
  'Low Risk':     { bg: 'bg-[var(--color-yellow-bg)]', text: 'text-[var(--color-yellow)]', border: 'border-[rgba(234,179,8,0.2)]',  dot: 'bg-[var(--color-yellow)] shadow-[0_0_6px_rgba(234,179,8,0.5)]' },
  'No Conflicts': { bg: 'bg-[var(--color-green-bg)]', text: 'text-[var(--color-green)]',  border: 'border-[rgba(34,197,94,0.2)]',  dot: 'bg-[var(--color-green)]  shadow-[0_0_6px_rgba(34,197,94,0.5)]' },
};

const labels = {
  High: 'High Risk', 'High Risk': 'High Risk',
  Medium: 'Medium Risk', 'Medium Risk': 'Medium Risk',
  Low: 'Low Risk', 'Low Risk': 'Low Risk',
  'No Conflicts': 'No Conflicts',
};

export default function RiskBadge({ risk, size = 'md' }) {
  const c = config[risk] || config.Low;
  const label = labels[risk] || risk;
  const sizeClass = size === 'lg' ? 'px-3.5 py-1 text-xs' : 'px-2.5 py-0.5 text-[11px]';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-semibold whitespace-nowrap ${c.bg} ${c.text} ${c.border} ${sizeClass}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${c.dot}`} />
      {label}
    </span>
  );
}
