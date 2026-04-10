import { useState } from 'react';
import Plot from 'react-plotly.js';
import TabBar from './ui/TabBar';
import MetricRating from './ui/MetricRating';
import { hackerLayout, STRATEGY_COLORS } from '../utils/plotTheme';
import type { EngineResultData, RunStatus } from '../types';

interface Props {
  results: EngineResultData[];
  onClear: () => void;
  progressPlots: { step: number; reward: number; entropy: number }[];
  runStatus: RunStatus;
  factorWeights: Record<string, number> | null;
}

export default function PerformanceArena({ results, onClear, progressPlots, runStatus, factorWeights }: Props) {
  const [resultIdx, setResultIdx] = useState(0);
  const [activeTab, setActiveTab] = useState('equity');
  const [equityOverlay, setEquityOverlay] = useState(false);

  // 训练进行中 — 实时双轴训练曲线（全屏）
  if (runStatus === 'running' && progressPlots.length > 0) {
    const steps = progressPlots.map(p => p.step);
    const rewards = progressPlots.map(p => p.reward);
    const entropies = progressPlots.map(p => p.entropy);
    return (
      <div className="w-full border border-border-base p-4 bg-bg-secondary" style={{ minHeight: 400 }}>
        <Plot
          data={[
            { x: steps, y: rewards, type: 'scatter', mode: 'lines', name: 'Cumulative Reward', line: { color: '#00FFFF', width: 2 } },
            { x: steps, y: entropies, type: 'scatter', mode: 'lines', name: 'Policy Entropy', line: { color: '#C724FF', width: 1.5, dash: 'dot' }, yaxis: 'y2' },
          ]}
          layout={hackerLayout({
            title: { text: '[LIVE DRL FUSION TRAINING]', font: { color: '#00FF41', size: 14 } },
            yaxis: { title: 'Reward', titlefont: { color: '#00FFFF' }, tickfont: { color: '#00FFFF' }, gridcolor: '#122012', color: '#00FF41' },
            yaxis2: { title: 'Entropy', titlefont: { color: '#C724FF' }, tickfont: { color: '#C724FF' }, overlaying: 'y', side: 'right', gridcolor: 'rgba(0,0,0,0)' },
            margin: { l: 50, r: 60, t: 50, b: 50 },
          })}
          useResizeHandler
          style={{ width: '100%', height: 360 }}
        />
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="h-[400px] flex flex-col items-center justify-center border border-border-dim text-text-muted gap-3">
        <div className="text-xl tracking-[10px]">AWAITING INSTRUCTIONS ...</div>
        <div className="text-caption text-text-muted">运行引擎后，结果将显示在这里</div>
      </div>
    );
  }

  const safeIdx = Math.min(resultIdx, results.length - 1);
  const result = results[safeIdx];
  const { engine, strategy_name, best_params, sharpe, calmar, max_drawdown, annual_return, equity_curve, extra_plots, weight_history, strategy_names } = result;

  const engineLc = engine.toLowerCase();
  const isDRL = engineLc.includes('drl') || engineLc.includes('deep') || engineLc.includes('reinforcement');
  const isGA = engineLc.includes('genetic') || engineLc.includes('ga');
  const isBayesian = engineLc.includes('bayesian') || engineLc.includes('optuna');

  const tabs = [{ id: 'equity', label: 'EQUITY' }];
  if ((isDRL || isGA) && weight_history && weight_history.length > 0) {
    tabs.push({ id: 'weights', label: 'WEIGHTS' });
  }
  if ((isBayesian && (extra_plots?.history || extra_plots?.importance)) ||
      (isGA && (extra_plots?.convergence?.length || extra_plots?.factor_weights))) {
    tabs.push({ id: 'optimization', label: 'OPTIMIZATION' });
  }
  tabs.push({ id: 'params', label: 'PARAMS' });
  // 多引擎对比 tab（≥2 个结果时显示）
  const multiEngine = results.length >= 2 && new Set(results.map(r => r.engine)).size >= 1;
  if (results.length >= 2) tabs.push({ id: 'compare', label: 'COMPARE' });

  const validTab = tabs.some(t => t.id === activeTab) ? activeTab : 'equity';

  // 因子权重：GA 用 extra_plots.factor_weights，Bayesian 用 WS factorWeights prop
  const fw = extra_plots?.factor_weights ?? (safeIdx === 0 ? factorWeights : null);

  return (
    <div className="flex flex-col gap-4">
      {/* 结果选择器 + 清除 */}
      <div className="flex flex-wrap gap-2 items-center border-b border-border-base pb-2">
        {results.map((r, i) => (
          <button
            key={i}
            onClick={() => { setResultIdx(i); setActiveTab('equity'); }}
            className={`text-caption uppercase tracking-wider px-3 py-1 border transition-colors ${
              i === safeIdx
                ? 'border-accent-emerald text-accent-emerald'
                : 'border-border-dim text-text-muted hover:border-border-bright hover:text-text-secondary'
            }`}
          >
            [{r.engine}] {r.strategy_name}
            {r.validation && <span className="ml-1 text-[9px] text-accent-amber">[OOS]</span>}
          </button>
        ))}
        <button
          onClick={onClear}
          className="ml-auto text-caption text-accent-magenta hover:text-text-primary transition-colors"
        >
          [CLEAR]
        </button>
      </div>

      {/* 核心指标卡 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Annual Return', value: `${(annual_return * 100).toFixed(2)}%`, positive: annual_return >= 0, rating: <MetricRating metric="annual" value={annual_return} /> },
          { label: 'Calmar Ratio',  value: calmar.toFixed(3),                      positive: calmar >= 1,        rating: <MetricRating metric="calmar" value={calmar} /> },
          { label: 'Max Drawdown', value: `${(max_drawdown * 100).toFixed(2)}%`,   positive: false,              rating: <MetricRating metric="maxdd"  value={max_drawdown} /> },
          { label: 'Sharpe Ratio', value: sharpe.toFixed(3),                       positive: sharpe >= 1,        rating: <MetricRating metric="sharpe" value={sharpe} /> },
        ].map(m => (
          <div key={m.label} className="border border-border-dim p-4 bg-bg-secondary text-center">
            <div className="text-caption text-text-muted mb-1 uppercase tracking-wider">{m.label}</div>
            <div className={`text-metric font-mono ${m.positive ? 'text-accent-emerald' : 'text-accent-magenta'}`}>
              {m.value}
            </div>
            <div className="mt-1 flex justify-center">{m.rating}</div>
          </div>
        ))}
      </div>

      {/* Tab 导航 */}
      <TabBar tabs={tabs} active={validTab} onChange={setActiveTab} />

      {/* Tab 内容区 */}
      <div className="border border-border-base p-4 bg-bg-secondary" style={{ minHeight: 360 }}>

        {/* EQUITY — OOS 权益曲线 */}
        {validTab === 'equity' && (
          <div>
            {results.length >= 2 && (
              <div className="flex justify-end mb-2">
                <button
                  onClick={() => setEquityOverlay(o => !o)}
                  className={`text-[11px] px-2 py-0.5 border font-mono transition-colors ${
                    equityOverlay
                      ? 'border-[#00FFFF] text-[#00FFFF] bg-[#00FFFF]/10'
                      : 'border-[#008F11]/50 text-[#008F11] hover:text-[#00FF41] hover:border-[#00FF41]'
                  }`}
                >
                  {equityOverlay ? '[OVERLAY ✓]' : '[OVERLAY]'}
                </button>
              </div>
            )}
            {equityOverlay && results.length >= 2 ? (
              <Plot
                data={results.map((r, i) => ({
                  y: r.equity_curve ?? [],
                  type: 'scatter' as const,
                  mode: 'lines' as const,
                  name: `[${r.engine}] ${r.strategy_name}`,
                  line: { color: STRATEGY_COLORS[i % STRATEGY_COLORS.length], width: 1.5 },
                }))}
                layout={hackerLayout({
                  title: { text: 'OOS Equity Overlay (All Results)', font: { color: '#00FF41', size: 13 } },
                  xaxis: { title: 'Bar', gridcolor: '#122012', color: '#00FF41' },
                  yaxis: { title: 'Cumulative Return', gridcolor: '#122012', color: '#00FF41' },
                  legend: { font: { color: '#008F11', size: 10 }, bgcolor: 'rgba(0,0,0,0.5)' },
                })}
                useResizeHandler
                style={{ width: '100%', height: 340 }}
              />
            ) : equity_curve && equity_curve.length > 0 ? (
              <Plot
                data={[{
                  y: equity_curve,
                  type: 'scatter', mode: 'lines', fill: 'tozeroy', name: 'OOS Equity',
                  line: { color: '#00FF41', width: 2 },
                  fillcolor: 'rgba(0,255,65,0.08)',
                }]}
                layout={hackerLayout({
                  title: { text: 'OOS Equity Curve (Simple Interest)', font: { color: '#00FF41', size: 13 } },
                  xaxis: { title: 'Bar', gridcolor: '#122012', color: '#00FF41' },
                  yaxis: { title: 'Cumulative Return', gridcolor: '#122012', color: '#00FF41' },
                })}
                useResizeHandler
                style={{ width: '100%', height: 340 }}
              />
            ) : (
              <div className="h-[340px] flex items-center justify-center text-text-muted text-caption">NO EQUITY DATA</div>
            )}
          </div>
        )}

        {/* WEIGHTS — 策略权重时序堆积面积图 */}
        {validTab === 'weights' && weight_history && weight_history.length > 0 && strategy_names && (
          <Plot
            data={strategy_names.map((name, i) => ({
              x: weight_history!.map((_, t) => t),
              y: weight_history!.map((w: number[]) => w[i] ?? 0),
              stackgroup: 'one',
              name,
              mode: 'lines' as const,
              line: { width: 0.5, color: STRATEGY_COLORS[i % STRATEGY_COLORS.length] },
              fillcolor: STRATEGY_COLORS[i % STRATEGY_COLORS.length],
            }))}
            layout={hackerLayout({
              title: { text: 'Strategy Weight Dynamics (OOS)', font: { color: '#00FFFF', size: 13 } },
              xaxis: { title: 'Timestep', gridcolor: '#122012', color: '#00FF41' },
              yaxis: { title: 'Weight', range: [0, 1], gridcolor: '#122012', color: '#00FF41' },
            })}
            useResizeHandler
            style={{ width: '100%', height: 340 }}
          />
        )}

        {/* OPTIMIZATION — Bayesian 图表 / GA 收敛图 + 因子权重 */}
        {validTab === 'optimization' && (
          <div className="flex flex-col gap-6">
            {/* Bayesian 优化历史散点图 */}
            {extra_plots?.history && (
              <Plot
                data={extra_plots.history.data as any}
                layout={{
                  ...(extra_plots.history.layout as any),
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                  font: { color: '#00FF41', family: 'monospace', size: 11 },
                }}
                useResizeHandler
                style={{ width: '100%', height: 300 }}
              />
            )}
            {/* Bayesian 参数重要性 */}
            {extra_plots?.importance && (
              <Plot
                data={extra_plots.importance.data as any}
                layout={{
                  ...(extra_plots.importance.layout as any),
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                  font: { color: '#C724FF', family: 'monospace', size: 11 },
                }}
                useResizeHandler
                style={{ width: '100%', height: 280 }}
              />
            )}
            {/* GA 适应度收敛曲线 */}
            {extra_plots?.convergence && extra_plots.convergence.length > 0 && (() => {
              const conv = extra_plots.convergence!;
              const phase1 = conv.filter(c => c.phase === 1);
              const phase2 = conv.filter(c => c.phase === 2);
              const traces: any[] = [];
              if (phase1.length > 0) {
                const strats = [...new Set(phase1.map(c => c.strategy))];
                strats.forEach((strat, si) => {
                  const pts = phase1.filter(c => c.strategy === strat);
                  traces.push({
                    x: pts.map(c => c.gen), y: pts.map(c => c.best_calmar),
                    type: 'scatter', mode: 'lines', name: `Ph1 ${strat}`,
                    line: { color: STRATEGY_COLORS[si % STRATEGY_COLORS.length], width: 1.5 },
                  });
                });
              }
              if (phase2.length > 0) {
                traces.push({
                  x: phase2.map(c => c.gen), y: phase2.map(c => c.best_calmar),
                  type: 'scatter', mode: 'lines', name: 'Ph2 Best Calmar',
                  line: { color: '#00FF41', width: 2.5 },
                });
                traces.push({
                  x: phase2.map(c => c.gen), y: phase2.map(c => c.std_calmar),
                  type: 'scatter', mode: 'lines', name: 'Ph2 Pop Std', yaxis: 'y2',
                  line: { color: '#C724FF', width: 1.5, dash: 'dot' },
                });
              }
              return (
                <Plot
                  data={traces}
                  layout={hackerLayout({
                    title: { text: '[GA] Fitness Convergence (Phase 1 & 2)', font: { color: '#00FF41', size: 13 } },
                    yaxis: { title: 'Best Calmar', titlefont: { color: '#00FF41' }, tickfont: { color: '#00FF41' }, gridcolor: '#122012' },
                    yaxis2: { title: 'Population Std', titlefont: { color: '#C724FF' }, tickfont: { color: '#C724FF' }, overlaying: 'y', side: 'right', gridcolor: 'rgba(0,0,0,0)' },
                    margin: { l: 55, r: 65, t: 50, b: 50 },
                  })}
                  useResizeHandler
                  style={{ width: '100%', height: 340 }}
                />
              );
            })()}
            {/* 因子权重饼图 */}
            {fw && Object.keys(fw).length > 0 && (
              <Plot
                data={[{
                  values: Object.values(fw),
                  labels: Object.keys(fw),
                  type: 'pie',
                  hole: 0.4,
                  marker: {
                    colors: Object.keys(fw).map((_, i) => STRATEGY_COLORS[i % STRATEGY_COLORS.length]),
                    line: { color: '#001a00', width: 1 },
                  },
                  textfont: { color: '#00FF41', family: 'monospace' },
                }]}
                layout={hackerLayout({
                  title: { text: 'Optimized Factor Weights', font: { color: '#C724FF', size: 13 } },
                  margin: { l: 20, r: 20, t: 50, b: 20 },
                })}
                useResizeHandler
                style={{ width: '100%', height: 320 }}
              />
            )}
          </div>
        )}

        {/* PARAMS — 最优参数 JSON */}
        {validTab === 'params' && (
          <div>
            <h3 className="text-caption text-accent-violet mb-3 uppercase tracking-widest">
              [FORGED OPTIMAL PARAMETERS]
            </h3>
            <pre className="text-accent-cyan text-caption overflow-auto leading-relaxed">
              {JSON.stringify(best_params, null, 2)}
            </pre>
          </div>
        )}

        {/* COMPARE — 多引擎横向对比 */}
        {validTab === 'compare' && (
          <div className="flex flex-col gap-6">
            {/* 对比表格 */}
            <div className="overflow-x-auto">
              <table className="w-full text-caption font-mono border-collapse">
                <thead>
                  <tr className="border-b border-border-base text-text-muted uppercase tracking-widest text-[10px]">
                    <th className="text-left py-2 pr-4">Engine</th>
                    <th className="text-left py-2 pr-4">Strategy</th>
                    <th className="text-right py-2 pr-4">Annual Ret</th>
                    <th className="text-right py-2 pr-4">Calmar</th>
                    <th className="text-right py-2 pr-4">Sharpe</th>
                    <th className="text-right py-2">Max DD</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => {
                    const best = results.reduce((a, b) => a.calmar > b.calmar ? a : b);
                    const isBest = r.calmar === best.calmar;
                    return (
                      <tr
                        key={i}
                        className={`border-b border-border-dim cursor-pointer transition-colors ${
                          i === safeIdx ? 'bg-accent-emerald/5' : 'hover:bg-border-dim/30'
                        }`}
                        onClick={() => { setResultIdx(i); setActiveTab('equity'); }}
                      >
                        <td className="py-2 pr-4 text-accent-cyan">{r.engine}</td>
                        <td className="py-2 pr-4 text-text-secondary truncate max-w-[120px]">{r.strategy_name}</td>
                        <td className={`py-2 pr-4 text-right ${r.annual_return >= 0 ? 'text-accent-emerald' : 'text-accent-magenta'}`}>
                          {(r.annual_return * 100).toFixed(2)}%
                        </td>
                        <td className={`py-2 pr-4 text-right font-bold ${isBest ? 'text-accent-amber' : r.calmar >= 1 ? 'text-accent-emerald' : 'text-accent-magenta'}`}>
                          {r.calmar.toFixed(3)}{isBest ? ' ★' : ''}
                        </td>
                        <td className={`py-2 pr-4 text-right ${r.sharpe >= 1 ? 'text-accent-emerald' : 'text-accent-magenta'}`}>
                          {r.sharpe.toFixed(3)}
                        </td>
                        <td className="py-2 text-right text-accent-magenta">
                          {(r.max_drawdown * 100).toFixed(2)}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Calmar / Sharpe 对比条形图 */}
            <Plot
              data={[
                {
                  x: results.map(r => `[${r.engine}] ${r.strategy_name}`),
                  y: results.map(r => r.calmar),
                  type: 'bar', name: 'Calmar',
                  marker: { color: results.map(r => r.calmar >= 1 ? '#00FF41' : '#C724FF') },
                },
                {
                  x: results.map(r => `[${r.engine}] ${r.strategy_name}`),
                  y: results.map(r => r.sharpe),
                  type: 'bar', name: 'Sharpe',
                  marker: { color: '#00FFFF', opacity: 0.7 },
                },
              ]}
              layout={hackerLayout({
                title: { text: 'Engine Comparison: Calmar & Sharpe', font: { color: '#00FF41', size: 13 } },
                barmode: 'group',
                xaxis: { tickangle: -20, gridcolor: '#122012', color: '#008F11' },
                yaxis: { gridcolor: '#122012', color: '#00FF41', zeroline: true, zerolinecolor: '#1A3A1A' },
                margin: { l: 50, r: 20, t: 50, b: 80 },
              })}
              useResizeHandler
              style={{ width: '100%', height: 340 }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
