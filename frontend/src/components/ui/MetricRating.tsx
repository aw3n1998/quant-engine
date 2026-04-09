interface Props {
  metric: 'sharpe' | 'calmar' | 'maxdd' | 'annual';
  value: number;
}

type Level = { label: string; color: string };

function getLevel(metric: Props['metric'], value: number): Level {
  switch (metric) {
    case 'sharpe':
      if (value >= 2)   return { label: '优秀', color: 'text-accent-emerald border-accent-emerald' };
      if (value >= 1.5) return { label: '良好', color: 'text-accent-cyan border-accent-cyan' };
      if (value >= 1)   return { label: '尚可', color: 'text-accent-amber border-accent-amber' };
      return              { label: '偏低', color: 'text-accent-magenta border-accent-magenta' };
    case 'calmar':
      if (value >= 1.5) return { label: '优秀', color: 'text-accent-emerald border-accent-emerald' };
      if (value >= 0.8) return { label: '良好', color: 'text-accent-cyan border-accent-cyan' };
      if (value >= 0.4) return { label: '尚可', color: 'text-accent-amber border-accent-amber' };
      return              { label: '偏低', color: 'text-accent-magenta border-accent-magenta' };
    case 'maxdd':
      if (value >= -0.05)  return { label: '优秀', color: 'text-accent-emerald border-accent-emerald' };
      if (value >= -0.15)  return { label: '良好', color: 'text-accent-cyan border-accent-cyan' };
      if (value >= -0.25)  return { label: '尚可', color: 'text-accent-amber border-accent-amber' };
      return                 { label: '偏高', color: 'text-accent-magenta border-accent-magenta' };
    case 'annual':
      if (value >= 0.30) return { label: '优秀', color: 'text-accent-emerald border-accent-emerald' };
      if (value >= 0.15) return { label: '良好', color: 'text-accent-cyan border-accent-cyan' };
      if (value >= 0.05) return { label: '尚可', color: 'text-accent-amber border-accent-amber' };
      return               { label: '偏低', color: 'text-accent-magenta border-accent-magenta' };
  }
}

export default function MetricRating({ metric, value }: Props) {
  const { label, color } = getLevel(metric, value);
  return (
    <span className={`text-[10px] px-1 border font-mono leading-none ${color}`}>
      ★ {label}
    </span>
  );
}
