import { useState } from "react";
import { runEngine } from "../services/api";

export default function ControlPanel({ connected }: { connected: boolean }) {
  // Global
  const [dataRows, setDataRows] = useState(2000);
  const [oosSplit, setOosSplit] = useState(20);
  
  // DRL
  const [targetRoi, setTargetRoi] = useState(10.0);
  const [maxDrawdown, setMaxDrawdown] = useState(-15.0);
  const [frictionPenalty, setFrictionPenalty] = useState(0.0005);
  const [ppoTimesteps, setPpoTimesteps] = useState(50000);
  
  // Bayesian
  const [optunaTrials, setOptunaTrials] = useState(100);
  const [wfvFolds, setWfvFolds] = useState(5);
  const [targetStrategies, setTargetStrategies] = useState(["fibonacci_resonance"]);

  const [running, setRunning] = useState(false);

  const strategyOptions = [
    "fibonacci_resonance", "mad_trend", "funding_arbitrage", 
    "po3_institutional", "orderflow_imbalance", "mev_capture",
    "statistical_pair", "nlp_event_driven", "dynamic_market_making",
    "liquidation_hunting", "liquidity_hedge_mining", "macro_capital_flow"
  ];

  const handleRun = async (engine: string) => {
    setRunning(true);
    try {
      await runEngine({
        engine,
        strategies: engine === 'drl' ? strategyOptions : targetStrategies,
        quick_mode: false,
        data_rows: dataRows,
        oos_split: oosSplit,
        target_roi: targetRoi,
        max_drawdown: maxDrawdown,
        friction_penalty: frictionPenalty,
        ppo_timesteps: ppoTimesteps,
        optuna_trials: optunaTrials,
        wfv_folds: wfvFolds
      });
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setTimeout(() => setRunning(false), 2000); // Debounce visual
    }
  };

  return (
    <div className="flex flex-col gap-6 text-sm">
      {/* Global Settings */}
      <section>
        <h3 className="uppercase font-bold mb-3 border-b border-[#008F11]/50 pb-1 text-[#00FFFF]">
          [GLOBAL SETTINGS]
        </h3>
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            Backtest Date Range (Rows)
            <input type="number" 
              className="matrix-input w-full" 
              value={dataRows} 
              onChange={e => setDataRows(Number(e.target.value))} />
          </label>
          <label className="flex flex-col gap-1">
            OOS Test Split % ( {oosSplit}% )
            <input type="range" 
              min={5} max={50} 
              value={oosSplit} 
              onChange={e => setOosSplit(Number(e.target.value))} />
          </label>
        </div>
      </section>

      {/* DRL Settings */}
      <section>
        <h3 className="uppercase font-bold mb-3 border-b border-[#008F11]/50 pb-1 text-[#C724FF]">
          [ENGINE A: DRL PIPELINE]
        </h3>
        <div className="flex flex-col gap-2">
          <label className="flex justify-between items-center">Target ROI %
            <input type="number" step="0.1" className="matrix-input w-24" value={targetRoi} onChange={e => setTargetRoi(Number(e.target.value))} />
          </label>
          <label className="flex justify-between items-center">Max Drawdown %
            <input type="number" step="0.1" className="matrix-input w-24" value={maxDrawdown} onChange={e => setMaxDrawdown(Number(e.target.value))} />
          </label>
          <label className="flex justify-between items-center">Friction Penalty
            <input type="number" step="0.0001" className="matrix-input w-24" value={frictionPenalty} onChange={e => setFrictionPenalty(Number(e.target.value))} />
          </label>
          <label className="flex justify-between items-center">PPO Timesteps
            <input type="number" step="1000" className="matrix-input w-24" value={ppoTimesteps} onChange={e => setPpoTimesteps(Number(e.target.value))} />
          </label>
        </div>
        <button 
          onClick={() => handleRun("drl")} 
          disabled={running || !connected}
          className="matrix-btn mt-4 py-2 w-full text-center">
          [INITIATE PPO FUSION]
        </button>
      </section>

      {/* Bayesian Settings */}
      <section>
        <h3 className="uppercase font-bold mb-3 border-b border-[#008F11]/50 pb-1 text-[#00FFFF]">
          [ENGINE B: BAYESIAN PIPELINE]
        </h3>
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1">Target Strategies
            <div className="flex flex-col gap-1 mt-1 max-h-32 overflow-y-auto border border-[#008F11]/50 p-2">
              {strategyOptions.map(o => (
                <label key={o} className="flex items-center gap-2 cursor-pointer text-[#00FFFF] hover:text-[#00FF41]">
                  <input 
                    type="checkbox" 
                    checked={targetStrategies.includes(o)} 
                    onChange={e => {
                      if (e.target.checked) setTargetStrategies(p => [...p, o]);
                      else setTargetStrategies(p => p.filter(x => x !== o));
                    }} 
                    className="accent-[#00FF41]"
                  />
                  <span>{o}</span>
                </label>
              ))}
            </div>
          </label>
          <label className="flex justify-between items-center">Optuna Trials
            <input type="number" step="10" className="matrix-input w-24" value={optunaTrials} onChange={e => setOptunaTrials(Number(e.target.value))} />
          </label>
          <label className="flex justify-between items-center">WFV Folds
            <input type="number" step="1" className="matrix-input w-24" value={wfvFolds} onChange={e => setWfvFolds(Number(e.target.value))} />
          </label>
        </div>
        <button 
          onClick={() => handleRun("bayesian")} 
          disabled={running || !connected}
          className="matrix-btn mt-4 py-2 w-full text-center">
          [FORGE OPTIMAL PARAMS]
        </button>
      </section>
    </div>
  );
}
