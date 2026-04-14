import { useState } from "react";
import { runBatchBacktest } from "../services/api";
import { STRATEGY_META } from "../data/glossary";
import GlowButton from "./ui/GlowButton";
import type { EngineResultData, BatchRunRequest } from "../types";

interface Props {
  onClose: () => void;
  baseParams: Omit<BatchRunRequest, "engines" | "timeframes" | "strategy_groups">;
  batchProgress: string;
  batchResults: EngineResultData[];
}

const ENGINE_OPTIONS = [
  { id: "bayesian", label: "Bayesian" },
  { id: "genetic", label: "Genetic" },
  { id: "montecarlo", label: "Monte Carlo" },
  { id: "drl", label: "DRL" }
];

const TIMEFRAMES = ["1d", "4h", "1h", "15m"];

const STRATEGY_GROUPS = [
  {
    id: "all_individual",
    label: "All Individually",
    getGroups: () => Object.keys(STRATEGY_META).map(s => [s])
  },
  {
    id: "trend_following",
    label: "Trend Following Group",
    getGroups: () => [["ema_trend_filter", "mad_trend", "donchian_breakout"]]
  },
  {
    id: "mean_reversion",
    label: "Mean Reversion Group",
    getGroups: () => [["bollinger_squeeze", "rsi_momentum"]]
  }
];

export default function BatchMatrixModal({ onClose, baseParams, batchProgress, batchResults }: Props) {
  const [selectedEngines, setSelectedEngines] = useState<string[]>(["bayesian"]);
  const [selectedTimeframes, setSelectedTimeframes] = useState<string[]>(["1h", "4h"]);
  const [selectedGroup, setSelectedGroup] = useState<string>("all_individual");
  const [running, setRunning] = useState(false);

  const toggleList = (list: string[], setter: (l: string[]) => void, item: string) => {
    setter(list.includes(item) ? list.filter(i => i !== item) : [...list, item]);
  };

  const handleStart = async () => {
    if (selectedEngines.length === 0 || selectedTimeframes.length === 0) return;
    
    setRunning(true);
    try {
      const groupConfig = STRATEGY_GROUPS.find(g => g.id === selectedGroup);
      const strategy_groups = groupConfig ? groupConfig.getGroups() : [["fibonacci_resonance"]];

      await runBatchBacktest({
        ...baseParams,
        engines: selectedEngines,
        timeframes: selectedTimeframes,
        strategy_groups
      });
    } catch (err) {
      console.error(err);
      alert("Failed to start batch: " + err);
    } finally {
      // The running state is mostly just for initiating the request
      // We could keep it true if we rely on ws run_status
      setRunning(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="bg-bg-secondary border border-border-base w-[800px] max-w-[95vw] max-h-[90vh] flex flex-col gap-4 overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border-base p-4 shrink-0">
          <span className="text-heading text-accent-magenta uppercase tracking-widest">
            [BATCH RUNNER MATRIX]
          </span>
          <button onClick={onClose} className="text-caption text-text-muted hover:text-accent-magenta transition-colors">
            [✕ CLOSE]
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
          <div className="grid grid-cols-3 gap-6">
            <div>
              <div className="text-caption text-accent-cyan uppercase mb-2">Engines</div>
              <div className="flex flex-col gap-2 border border-border-dim p-2">
                {ENGINE_OPTIONS.map(eng => (
                  <label key={eng.id} className="flex items-center gap-2 cursor-pointer text-caption text-text-secondary hover:text-text-primary">
                    <input type="checkbox" checked={selectedEngines.includes(eng.id)} onChange={() => toggleList(selectedEngines, setSelectedEngines, eng.id)} className="accent-accent-magenta" />
                    {eng.label}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <div className="text-caption text-accent-cyan uppercase mb-2">Timeframes</div>
              <div className="flex flex-col gap-2 border border-border-dim p-2">
                {TIMEFRAMES.map(tf => (
                  <label key={tf} className="flex items-center gap-2 cursor-pointer text-caption text-text-secondary hover:text-text-primary">
                    <input type="checkbox" checked={selectedTimeframes.includes(tf)} onChange={() => toggleList(selectedTimeframes, setSelectedTimeframes, tf)} className="accent-accent-magenta" />
                    {tf.toUpperCase()}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <div className="text-caption text-accent-cyan uppercase mb-2">Strategy Groups</div>
              <div className="flex flex-col gap-2 border border-border-dim p-2">
                {STRATEGY_GROUPS.map(grp => (
                  <label key={grp.id} className="flex items-center gap-2 cursor-pointer text-caption text-text-secondary hover:text-text-primary">
                    <input type="radio" name="strategyGroup" checked={selectedGroup === grp.id} onChange={() => setSelectedGroup(grp.id)} className="accent-accent-magenta" />
                    {grp.label}
                  </label>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between mt-2">
            <div className="text-caption text-text-muted font-mono flex-1">
              {batchProgress ? `> ${batchProgress}` : '> READY TO INITIATE MATRIX RUN...'}
            </div>
            <div className="w-48 shrink-0">
              <GlowButton fullWidth onClick={handleStart} disabled={running}>
                {running ? '[STARTING...]' : '[INITIATE BATCH]'}
              </GlowButton>
            </div>
          </div>

          <div className="flex-1 flex flex-col min-h-[300px] border border-border-base bg-bg-primary">
            <div className="flex items-center justify-between p-2 border-b border-border-base bg-bg-secondary">
              <span className="text-caption uppercase text-accent-cyan tracking-widest">Live Results</span>
              <span className="text-caption text-text-muted">Count: {batchResults.length}</span>
            </div>
            <div className="flex-1 overflow-auto p-2">
              <table className="w-full text-caption font-mono text-left border-collapse">
                <thead>
                  <tr className="border-b border-border-dim text-text-muted">
                    <th className="py-1 px-2 font-normal">Engine</th>
                    <th className="py-1 px-2 font-normal">TF</th>
                    <th className="py-1 px-2 font-normal">Strategy</th>
                    <th className="py-1 px-2 font-normal text-right">Sharpe</th>
                    <th className="py-1 px-2 font-normal text-right">Return</th>
                  </tr>
                </thead>
                <tbody>
                  {[...batchResults]
                    .sort((a, b) => b.sharpe - a.sharpe)
                    .map((res, i) => (
                      <tr key={i} className="border-b border-border-dim/50 hover:bg-border-base/30">
                        <td className="py-1 px-2 text-accent-cyan">{res.engine}</td>
                        <td className="py-1 px-2 text-text-secondary">{(res.best_params?.timeframe as string) || "N/A"}</td>
                        <td className="py-1 px-2 max-w-[200px] truncate" title={res.strategy_name}>{res.strategy_name}</td>
                        <td className={`py-1 px-2 text-right ${res.sharpe > 1.5 ? 'text-accent-emerald' : res.sharpe < 0 ? 'text-accent-magenta' : 'text-text-primary'}`}>
                          {res.sharpe.toFixed(2)}
                        </td>
                        <td className="py-1 px-2 text-right text-text-secondary">
                          {(res.annual_return * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  {batchResults.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-4 text-center text-text-muted italic">
                        No batch results yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
