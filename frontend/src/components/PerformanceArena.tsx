import Plot from 'react-plotly.js';
import type { EngineResultData, RunStatus } from '../types';

// 12色赛博朋克调色板，交替使用青/绿/紫/品红色系
const STRATEGY_COLORS = [
  '#00FFFF', '#00FF41', '#C724FF', '#FF00A0',
  '#00BFFF', '#39FF14', '#9D00FF', '#FF6EC7',
  '#00E5FF', '#ADFF2F', '#7B00D4', '#FF69B4',
];

interface PerformanceArenaProps {
  results: EngineResultData[];
  onClear: () => void;
  progressPlots: { step: number; reward: number; entropy: number }[];
  runStatus: RunStatus;
  factorWeights: Record<string, number> | null;
}

export default function PerformanceArena({
  results,
  onClear,
  progressPlots,
  runStatus,
  factorWeights,
}: PerformanceArenaProps) {
  // 训练进行中 — 实时双轴训练曲线
  if (runStatus === 'running' && progressPlots.length > 0) {
    const steps = progressPlots.map(p => p.step);
    const rewards = progressPlots.map(p => p.reward);
    const entropies = progressPlots.map(p => p.entropy);

    return (
      <div className="w-full flex justify-center border border-[#008F11] p-4 bg-[#0a110a] relative min-h-[400px]">
        <Plot
          data={[
            {
              x: steps,
              y: rewards,
              type: 'scatter',
              mode: 'lines',
              name: 'Cumulative Reward',
              line: { color: '#00FFFF', width: 2 },
            },
            {
              x: steps,
              y: entropies,
              type: 'scatter',
              mode: 'lines',
              name: 'Policy Entropy',
              line: { color: '#C724FF', width: 1.5, dash: 'dot' },
              yaxis: 'y2',
            },
          ]}
          layout={{
            title: { text: '[LIVE DRL FUSION TRAINING]', font: { color: '#00FF41', size: 14 } },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#00FF41', family: 'monospace' },
            xaxis: { title: 'Timesteps', gridcolor: '#001a00', color: '#00FF41' },
            yaxis: {
              title: 'Reward',
              titlefont: { color: '#00FFFF' },
              tickfont: { color: '#00FFFF' },
              gridcolor: '#001a00',
            },
            yaxis2: {
              title: 'Entropy',
              titlefont: { color: '#C724FF' },
              tickfont: { color: '#C724FF' },
              overlaying: 'y',
              side: 'right',
              gridcolor: 'rgba(0,0,0,0)',
            },
            legend: { font: { color: '#00FF41' }, bgcolor: 'rgba(0,0,0,0)' },
            margin: { l: 50, r: 60, t: 50, b: 50 },
          } as any}
          useResizeHandler={true}
          style={{ width: '100%', height: '100%', minHeight: 360 }}
        />
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="h-[400px] flex items-center justify-center border border-[#008F11]/30 text-[#008F11] text-xl tracking-[10px]">
        AWAITING INSTRUCTIONS ...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-12">
      {results.map((result, idx) => {
        const {
          engine,
          strategy_name,
          best_params,
          sharpe,
          calmar,
          max_drawdown,
          annual_return,
          equity_curve,
          extra_plots,
          weight_history,
          strategy_names,
        } = result;

        // 因子权重：GA 用 extra_plots.factor_weights，Bayesian 用 factorWeights prop（第一条结果）
        const fw: Record<string, number> | null | undefined =
          extra_plots?.factor_weights ?? (idx === 0 ? factorWeights : null);

        return (
          <div key={idx} className="flex flex-col gap-6">
            {/* 标题行 */}
            <div className="flex justify-between items-center border-b border-[#008F11] pb-2">
              <h2 className="text-xl uppercase tracking-widest">
                [ {engine} ] {strategy_name}
              </h2>
              {idx === 0 && (
                <button
                  onClick={onClear}
                  className="text-[#C724FF] hover:text-[#00FF41] text-sm tracking-widest transition-colors"
                >
                  [CLEAR]
                </button>
              )}
            </div>

            {/* 核心指标 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Annual Return', value: `${(annual_return * 100).toFixed(2)}%` },
                { label: 'Calmar Ratio',  value: calmar.toFixed(3) },
                { label: 'Max Drawdown',  value: `${(max_drawdown * 100).toFixed(2)}%` },
                { label: 'Sharpe Ratio',  value: sharpe.toFixed(3) },
              ].map(m => (
                <div
                  key={m.label}
                  className="border border-[#00FF41]/30 p-4 bg-[#0a110a] text-center"
                >
                  <div className="text-xs text-[#008F11] mb-1 uppercase tracking-wider">{m.label}</div>
                  <div className="text-2xl font-mono">{m.value}</div>
                </div>
              ))}
            </div>

            {/* OOS 权益曲线 */}
            {equity_curve && equity_curve.length > 0 && (
              <div className="border border-[#008F11] p-4 bg-[#0a110a]" style={{ height: 360 }}>
                <Plot
                  data={[
                    {
                      y: equity_curve,
                      type: 'scatter',
                      mode: 'lines',
                      fill: 'tozeroy',
                      name: 'OOS Equity',
                      line: { color: '#00FF41', width: 2 },
                      fillcolor: 'rgba(0, 255, 65, 0.08)',
                    },
                  ]}
                  layout={{
                    title: { text: 'OOS Equity Curve (Simple Interest)', font: { color: '#00FF41', size: 13 } },
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    font: { color: '#00FF41', family: 'monospace' },
                    xaxis: { title: 'Bar', gridcolor: '#001a00', color: '#00FF41' },
                    yaxis: { title: 'Return', gridcolor: '#001a00', color: '#00FF41' },
                    margin: { l: 50, r: 20, t: 45, b: 45 },
                  } as any}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                />
              </div>
            )}

            {/* 策略权重时序堆积面积图（DRL / GA Phase-2） */}
            {weight_history && weight_history.length > 0 && strategy_names && strategy_names.length > 0 && (
              <div className="border border-[#008F11] p-4 bg-[#0a110a]" style={{ height: 320 }}>
                <Plot
                  data={strategy_names.map((name, i) => ({
                    x: weight_history!.map((_: number[], t: number) => t),
                    y: weight_history!.map((w: number[]) => w[i] ?? 0),
                    stackgroup: 'one',
                    name,
                    mode: 'lines' as const,
                    line: { width: 0.5, color: STRATEGY_COLORS[i % STRATEGY_COLORS.length] },
                    fillcolor: STRATEGY_COLORS[i % STRATEGY_COLORS.length],
                  }))}
                  layout={{
                    title: { text: 'Strategy Weight Dynamics (OOS)', font: { color: '#00FFFF', size: 13 } },
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    font: { color: '#00FF41', family: 'monospace' },
                    xaxis: { title: 'Timestep', gridcolor: '#001a00', color: '#00FF41' },
                    yaxis: { title: 'Weight', range: [0, 1], gridcolor: '#001a00', color: '#00FF41' },
                    legend: { font: { color: '#00FF41', size: 10 }, bgcolor: 'rgba(0,0,0,0)' },
                    margin: { l: 50, r: 20, t: 45, b: 45 },
                  } as any}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                />
              </div>
            )}

            {/* Bayesian 优化历史散点图 */}
            {extra_plots?.history && (
              <div className="border border-[#008F11] p-4 bg-[#0a110a]" style={{ height: 380 }}>
                <Plot
                  data={extra_plots.history.data as any}
                  layout={{
                    ...(extra_plots.history.layout as any),
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    font: { color: '#00FF41', family: 'monospace' },
                  }}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                />
              </div>
            )}

            {/* Bayesian 参数重要性条形图 */}
            {extra_plots?.importance && (
              <div className="border border-[#008F11] p-4 bg-[#0a110a]" style={{ height: 360 }}>
                <Plot
                  data={extra_plots.importance.data as any}
                  layout={{
                    ...(extra_plots.importance.layout as any),
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    font: { color: '#C724FF', family: 'monospace' },
                  }}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                />
              </div>
            )}

            {/* GA 适应度收敛曲线（双轴：Best Calmar + 种群标准差） */}
            {extra_plots?.convergence && extra_plots.convergence.length > 0 && (() => {
              const conv = extra_plots.convergence!;
              const phase1 = conv.filter(c => c.phase === 1);
              const phase2 = conv.filter(c => c.phase === 2);

              const traces: any[] = [];
              if (phase1.length > 0) {
                const strategies = [...new Set(phase1.map(c => c.strategy))];
                strategies.forEach((strat, si) => {
                  const pts = phase1.filter(c => c.strategy === strat);
                  traces.push({
                    x: pts.map(c => c.gen),
                    y: pts.map(c => c.best_calmar),
                    type: 'scatter', mode: 'lines',
                    name: `Ph1 ${strat}`,
                    line: { color: STRATEGY_COLORS[si % STRATEGY_COLORS.length], width: 1.5 },
                  });
                });
              }
              if (phase2.length > 0) {
                traces.push({
                  x: phase2.map(c => c.gen),
                  y: phase2.map(c => c.best_calmar),
                  type: 'scatter', mode: 'lines',
                  name: 'Ph2 Factor Weights Best',
                  line: { color: '#00FF41', width: 2.5 },
                });
                traces.push({
                  x: phase2.map(c => c.gen),
                  y: phase2.map(c => c.std_calmar),
                  type: 'scatter', mode: 'lines',
                  name: 'Ph2 Pop Std',
                  line: { color: '#C724FF', width: 1.5, dash: 'dot' },
                  yaxis: 'y2',
                });
              }

              return (
                <div className="border border-[#008F11] p-4 bg-[#0a110a]" style={{ height: 380 }}>
                  <Plot
                    data={traces}
                    layout={{
                      title: { text: '[GA] Fitness Convergence (Phase 1 & 2)', font: { color: '#00FF41', size: 13 } },
                      paper_bgcolor: 'transparent',
                      plot_bgcolor: 'transparent',
                      font: { color: '#00FF41', family: 'monospace' },
                      xaxis: { title: 'Generation', gridcolor: '#001a00', color: '#00FF41' },
                      yaxis: {
                        title: 'Best Calmar',
                        titlefont: { color: '#00FF41' },
                        tickfont: { color: '#00FF41' },
                        gridcolor: '#001a00',
                      },
                      yaxis2: {
                        title: 'Population Std',
                        titlefont: { color: '#C724FF' },
                        tickfont: { color: '#C724FF' },
                        overlaying: 'y',
                        side: 'right',
                        gridcolor: 'rgba(0,0,0,0)',
                      },
                      legend: { font: { color: '#00FF41', size: 9 }, bgcolor: 'rgba(0,0,0,0)' },
                      margin: { l: 55, r: 65, t: 50, b: 50 },
                    } as any}
                    useResizeHandler={true}
                    style={{ width: '100%', height: '100%' }}
                  />
                </div>
              );
            })()}

            {/* 因子权重饼图（GA extra_plots.factor_weights 或 Bayesian factorWeights WS） */}
            {fw && Object.keys(fw).length > 0 && (
              <div className="border border-[#C724FF]/40 p-4 bg-[#0a110a]" style={{ height: 360 }}>
                <Plot
                  data={[
                    {
                      values: Object.values(fw),
                      labels: Object.keys(fw),
                      type: 'pie',
                      hole: 0.4,
                      marker: {
                        colors: Object.keys(fw).map((_, i) => STRATEGY_COLORS[i % STRATEGY_COLORS.length]),
                        line: { color: '#001a00', width: 1 },
                      },
                      textfont: { color: '#00FF41', family: 'monospace' },
                    },
                  ]}
                  layout={{
                    title: { text: 'Optimized Factor Weights', font: { color: '#C724FF', size: 13 } },
                    paper_bgcolor: 'transparent',
                    font: { color: '#00FF41', family: 'monospace' },
                    legend: { font: { color: '#00FF41', size: 10 }, bgcolor: 'rgba(0,0,0,0)' },
                    margin: { l: 20, r: 20, t: 50, b: 20 },
                  } as any}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                />
              </div>
            )}

            {/* 最优参数原始展示 */}
            <div className="border border-[#008F11] p-4 bg-[#050a05]">
              <h3 className="text-sm text-[#C724FF] mb-2 uppercase tracking-widest">
                [FORGED OPTIMAL PARAMETERS]
              </h3>
              <pre className="text-[#00FFFF] text-xs overflow-auto">
                {JSON.stringify(best_params, null, 2)}
              </pre>
            </div>
          </div>
        );
      })}
    </div>
  );
}
