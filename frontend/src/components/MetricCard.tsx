// frontend/src/components/MetricCard.tsx

import { formatPercent, formatNumber } from "../utils/formatters";

interface MetricCardProps {
  label: string;
  value: number;
  isPercent?: boolean;
  colorClass?: string;
}

export default function MetricCard({
  label,
  value,
  isPercent = false,
  colorClass = "text-accent-cyan",
}: MetricCardProps) {
  const displayValue = isPercent ? formatPercent(value) : formatNumber(value);

  return (
    <div className="relative overflow-hidden rounded-xl border border-surface-700/50 bg-surface-800/60 p-4 backdrop-blur-sm transition-all duration-300 hover:border-surface-600/80 hover:bg-surface-800/80">
      <div className="absolute -right-4 -top-4 h-16 w-16 rounded-full bg-gradient-to-br from-accent-violet/10 to-accent-cyan/10 blur-2xl" />
      <p className="mb-1 text-xs font-medium uppercase tracking-wider text-surface-400">
        {label}
      </p>
      <p className={`text-2xl font-semibold tabular-nums ${colorClass}`}>
        {displayValue}
      </p>
    </div>
  );
}
