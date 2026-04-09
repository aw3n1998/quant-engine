export function hackerLayout(overrides?: Record<string, unknown>): Record<string, unknown> {
  return {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: '#00FF41', family: 'JetBrains Mono, monospace', size: 11 },
    xaxis: { gridcolor: '#122012', color: '#00FF41', zerolinecolor: '#1A3A1A' },
    yaxis: { gridcolor: '#122012', color: '#00FF41', zerolinecolor: '#1A3A1A' },
    legend: { font: { color: '#00FF41', size: 10 }, bgcolor: 'rgba(0,0,0,0)' },
    margin: { l: 50, r: 20, t: 40, b: 40 },
    ...overrides,
  };
}

export const STRATEGY_COLORS = [
  '#00FFFF', '#00FF41', '#C724FF', '#FF00A0',
  '#00BFFF', '#39FF14', '#9D00FF', '#FF6EC7',
  '#00E5FF', '#ADFF2F', '#7B00D4', '#FF69B4',
];
