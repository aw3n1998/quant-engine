interface MetricCardProps {
  label: string;
  value: string;
  positive?: boolean;
}

export default function MetricCard({ label, value, positive }: MetricCardProps) {
  const valueColor = positive === undefined
    ? 'text-text-primary'
    : positive
      ? 'text-accent-emerald'
      : 'text-accent-magenta';

  return (
    <div className="border border-border-base bg-bg-secondary p-4 text-center hover:border-border-bright transition-colors">
      <div className="text-caption text-text-secondary uppercase tracking-widest mb-1">{label}</div>
      <div className={`text-metric font-mono ${valueColor}`}>{value}</div>
    </div>
  );
}
