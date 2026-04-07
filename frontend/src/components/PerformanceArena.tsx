import Plot from 'react-plotly.js';
import type { EngineResultData } from '../types';

interface PerformanceArenaProps {
  results: EngineResultData[];
  onClear: () => void;
  progressPlots: { step: number; reward: number; entropy: number }[];
  status: 'idle' | 'running' | 'done' | 'error';
}

export default function PerformanceArena({ results, onClear, progressPlots, status }: PerformanceArenaProps) {
  if (status === 'running' && progressPlots.length > 0) {
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
              name: 'Reward',
              line: { color: '#00FFFF' },
            },
            {
              x: steps,
              y: entropies,
              type: 'scatter',
              mode: 'lines',
              name: 'Entropy',
              line: { color: '#006400' },
              yaxis: 'y2',
            }
          ]}
          layout={{
            title: '[LIVE DRL FUSION TRAINING]',
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#00FF41' },
            xaxis: { title: 'Timesteps' },
            yaxis: { title: 'Reward', titlefont: { color: '#00FFFF' }, tickfont: { color: '#00FFFF' } },
            yaxis2: { title: 'Entropy', titlefont: { color: '#006400' }, tickfont: { color: '#006400' }, overlaying: 'y', side: 'right' },
            margin: { l: 40, r: 40, t: 40, b: 40 },
          } as any}
          useResizeHandler={true}
          style={{ width: "100%", height: "100%" }}
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
        const { engine, strategy_name, best_params, sharpe, calmar, max_drawdown, annual_return, equity_curve, extra_plots } = result;
        return (
          <div key={idx} className="flex flex-col gap-6">
            <div className="flex justify-between items-center border-b border-[#008F11] pb-2">
              <h2 className="text-xl uppercase">[ {engine} ] {strategy_name} RESULT</h2>
              {idx === 0 && <button onClick={onClear} className="text-[#c724ff] hover:text-[#00FF41]">[CLEAR]</button>}
            </div>

            {/* Metrics Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Total Return', value: `${(annual_return * 100).toFixed(2)}%` },
                { label: 'Calmar Ratio', value: calmar.toFixed(2) },
                { label: 'Max Drawdown', value: `${(max_drawdown * 100).toFixed(2)}%` },
                { label: 'Sharpe Ratio', value: sharpe.toFixed(2) },
              ].map(m => (
                <div key={m.label} className="border border-[#00FF41]/30 p-4 bg-[#0a110a] text-center">
                  <div className="text-xs text-[#008F11] mb-1">{m.label}</div>
                  <div className="text-2xl text-shadow-neon">{m.value}</div>
                </div>
              ))}
            </div>

            {/* Equity Curve */}
            {equity_curve && equity_curve.length > 0 && (
              <div className="border border-[#008F11] p-4 bg-[#0a110a] h-[400px]">
                <Plot
                  data={[
                    {
                      y: equity_curve,
                      type: 'scatter',
                      mode: 'lines',
                      fill: 'tozeroy',
                      line: { color: '#00FF41' },
                      fillcolor: 'rgba(0, 255, 65, 0.1)'
                    }
                  ]}
                  layout={{
                    title: 'OOS Equity Curve (Simple Interest)',
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    font: { color: '#00FF41' },
                    margin: { l: 40, r: 20, t: 40, b: 40 },
                  } as any}
                  useResizeHandler={true}
                  style={{ width: "100%", height: "100%" }}
                />
              </div>
            )}

            {/* Extra Plots for Bayesian (Objective History + Param Importances) */}
            {extra_plots && extra_plots.history && (
              <div className="border border-[#008F11] p-4 bg-[#0a110a] h-[400px]">
                <Plot
                  data={extra_plots.history.data}
                  layout={{
                    ...extra_plots.history.layout,
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    font: { color: '#00FF41' },
                  } as any}
                  useResizeHandler={true}
                  style={{ width: "100%", height: "100%" }}
                />
              </div>
            )}
            
            {extra_plots && extra_plots.importance && (
              <div className="border border-[#008F11] p-4 bg-[#0a110a] h-[400px] mt-4">
                <Plot
                  data={extra_plots.importance.data}
                  layout={{
                    ...extra_plots.importance.layout,
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    font: { color: '#C724FF' },
                  } as any}
                  useResizeHandler={true}
                  style={{ width: "100%", height: "100%" }}
                />
              </div>
            )}

            {/* Optimum params block */}
            <div className="border border-[#008F11] p-4 bg-[#050a05]">
              <h3 className="text-sm text-[#C724FF] mb-2 uppercase">[FORGED OPTIMAL PARAMETERS]</h3>
              <pre className="text-[#00FFFF] text-xs">
                {JSON.stringify(best_params, null, 2)}
              </pre>
            </div>
          </div>
        );
      })}
    </div>
  );
}
