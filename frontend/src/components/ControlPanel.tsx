import { useState, useRef } from "react";
import { runEngine, uploadData } from "../services/api";
import type { RunStatus } from "../types";
import BinanceFetcher from "./BinanceFetcher";
import TerminalSection from "./ui/TerminalSection";
import GlowButton from "./ui/GlowButton";
import NeonInput from "./ui/NeonInput";

const STRATEGY_OPTIONS = [
  "fibonacci_resonance", "mad_trend", "funding_arbitrage",
  "po3_institutional", "orderflow_imbalance", "mev_capture",
  "statistical_pair", "nlp_event_driven", "dynamic_market_making",
  "liquidation_hunting", "liquidity_hedge_mining", "macro_capital_flow",
];

const TIMEFRAMES = [
  { value: "1d",  label: "1D 日线" },
  { value: "4h",  label: "4H 四小时" },
  { value: "1h",  label: "1H 小时" },
  { value: "30m", label: "30M 半小时" },
  { value: "15m", label: "15M 十五分钟" },
  { value: "5m",  label: "5M 五分钟" },
];

const PRESETS = {
  quick:    { dataRows: 500,  ppoTimesteps: 10000,  optunaTrials: 20,  gaPopulation: 15, gaGenerations: 8 },
  standard: { dataRows: 2000, ppoTimesteps: 50000,  optunaTrials: 80,  gaPopulation: 40, gaGenerations: 25 },
  deep:     { dataRows: 5000, ppoTimesteps: 200000, optunaTrials: 200, gaPopulation: 60, gaGenerations: 50 },
};

type DataSource = "synthetic" | "csv" | "binance";

interface Props {
  connected: boolean;
  runStatus: RunStatus;
}

export default function ControlPanel({ connected, runStatus }: Props) {
  const running = runStatus === 'running';
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [dataSource, setDataSource] = useState<DataSource>("synthetic");
  const [dataRows, setDataRows] = useState(2000);
  const [dataInfo, setDataInfo] = useState<string | null>(null);
  const [oosSplit, setOosSplit] = useState(20);
  const [timeframe, setTimeframe] = useState("1d");
  const [targetRoi, setTargetRoi] = useState(10.0);
  const [maxDrawdown, setMaxDrawdown] = useState(-15.0);
  const [frictionPenalty, setFrictionPenalty] = useState(0.0005);
  const [ppoTimesteps, setPpoTimesteps] = useState(50000);
  const [optunaTrials, setOptunaTrials] = useState(80);
  const [wfvFolds, setWfvFolds] = useState(5);
  const [bayesianStrategies, setBayesianStrategies] = useState(["fibonacci_resonance"]);
  const [gaStrategies, setGaStrategies] = useState(["fibonacci_resonance", "mad_trend"]);
  const [gaPopulation, setGaPopulation] = useState(40);
  const [gaGenerations, setGaGenerations] = useState(25);

  const applyPreset = (key: keyof typeof PRESETS) => {
    const p = PRESETS[key];
    setDataRows(p.dataRows);
    setPpoTimesteps(p.ppoTimesteps);
    setOptunaTrials(p.optunaTrials);
    setGaPopulation(p.gaPopulation);
    setGaGenerations(p.gaGenerations);
  };

  const buildCommonParams = () => ({
    quick_mode: false, data_rows: dataRows, oos_split: oosSplit,
    timeframe, target_roi: targetRoi, max_drawdown: maxDrawdown,
    friction_penalty: frictionPenalty, ppo_timesteps: ppoTimesteps,
    optuna_trials: optunaTrials, wfv_folds: wfvFolds,
    ga_population: gaPopulation, ga_generations: gaGenerations,
  });

  const handleRun = async (engine: string, strategies: string[]) => {
    if (strategies.length === 0) return;
    try { await runEngine({ engine, strategies, ...buildCommonParams() }); }
    catch (err) { console.error(err); }
  };

  const handleCSVUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await uploadData(file);
      setDataInfo(`CSV: ${res.rows} rows`);
    } catch (err: unknown) {
      alert(`Upload failed: ${err instanceof Error ? err.message : err}`);
    }
  };

  const toggleStrategy = (list: string[], setter: React.Dispatch<React.SetStateAction<string[]>>, sid: string, checked: boolean) => {
    setter(checked ? [...list, sid] : list.filter(x => x !== sid));
  };

  return (
    <div className="flex flex-col gap-3">
      {/* Presets */}
      <div className="flex gap-2">
        {(Object.keys(PRESETS) as (keyof typeof PRESETS)[]).map(k => (
          <GlowButton key={k} size="sm" onClick={() => applyPreset(k)}>
            {k.toUpperCase()}
          </GlowButton>
        ))}
      </div>

      {/* Data Source */}
      <TerminalSection title="DATA SOURCE" accent="cyan" defaultOpen>
        <div className="flex gap-3 mb-3 text-caption">
          {(["synthetic", "csv", "binance"] as DataSource[]).map(ds => (
            <label key={ds} className="flex items-center gap-1 cursor-pointer">
              <input type="radio" name="datasource" value={ds} checked={dataSource === ds}
                onChange={() => setDataSource(ds)} className="accent-accent-emerald" />
              <span className={dataSource === ds ? "text-text-primary" : "text-text-secondary"}>
                {ds === "synthetic" ? "Synthetic" : ds === "csv" ? "CSV" : "Binance"}
              </span>
            </label>
          ))}
        </div>
        {dataSource === "synthetic" && (
          <NeonInput type="number" label="K-lines" value={dataRows} onChange={v => setDataRows(Number(v))} min={500} max={20000} step={500} />
        )}
        {dataSource === "csv" && (
          <div className="flex flex-col gap-2">
            <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleCSVUpload} />
            <GlowButton size="sm" onClick={() => fileInputRef.current?.click()}>[Upload CSV]</GlowButton>
            {dataInfo && <div className="text-caption text-accent-emerald">{dataInfo}</div>}
          </div>
        )}
        {dataSource === "binance" && (
          <BinanceFetcher onLoaded={info => setDataInfo(`${info.symbol} ${info.timeframe} x ${info.rows}`)} />
        )}
      </TerminalSection>

      {/* Global */}
      <TerminalSection title="GLOBAL SETTINGS" accent="cyan" collapsible defaultOpen={false}>
        <div className="flex flex-col gap-2">
          <NeonInput type="select" label="Timeframe" value={timeframe} onChange={setTimeframe} layout="col"
            options={TIMEFRAMES} />
          <NeonInput type="range" label="OOS Split" value={oosSplit} onChange={v => setOosSplit(Number(v))}
            min={5} max={50} suffix="%" />
        </div>
      </TerminalSection>

      {/* Engine A: DRL */}
      <TerminalSection title="ENGINE A: DRL PIPELINE" accent="magenta" collapsible defaultOpen={false}>
        <div className="flex flex-col gap-2">
          <NeonInput type="number" label="Target ROI %" value={targetRoi} onChange={v => setTargetRoi(Number(v))} step={0.1} />
          <NeonInput type="number" label="Max DD %" value={maxDrawdown} onChange={v => setMaxDrawdown(Number(v))} step={0.1} />
          <NeonInput type="number" label="Friction" value={frictionPenalty} onChange={v => setFrictionPenalty(Number(v))} step={0.0001} />
          <NeonInput type="number" label="PPO Steps" value={ppoTimesteps} onChange={v => setPpoTimesteps(Number(v))} step={1000} />
        </div>
        <GlowButton fullWidth onClick={() => handleRun("drl", STRATEGY_OPTIONS)} disabled={running || !connected} loading={running}>
          [INITIATE PPO FUSION]
        </GlowButton>
      </TerminalSection>

      {/* Engine B: Bayesian */}
      <TerminalSection title="ENGINE B: BAYESIAN" accent="cyan" collapsible defaultOpen={false}>
        <div className="flex flex-col gap-2">
          <div className="text-caption text-text-secondary mb-1">Target Strategies</div>
          <div className="max-h-28 overflow-y-auto border border-border-dim p-2 flex flex-col gap-1">
            {STRATEGY_OPTIONS.map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer text-caption hover:text-text-primary transition-colors">
                <input type="checkbox" checked={bayesianStrategies.includes(s)}
                  onChange={e => toggleStrategy(bayesianStrategies, setBayesianStrategies, s, e.target.checked)}
                  className="accent-accent-emerald" />
                <span>{s}</span>
              </label>
            ))}
          </div>
          <NeonInput type="number" label="Trials" value={optunaTrials} onChange={v => setOptunaTrials(Number(v))} step={10} />
          <NeonInput type="number" label="WFV Folds" value={wfvFolds} onChange={v => setWfvFolds(Number(v))} min={2} max={10} step={1} />
        </div>
        <GlowButton fullWidth onClick={() => handleRun("bayesian", bayesianStrategies)}
          disabled={running || !connected || bayesianStrategies.length === 0} loading={running}>
          [FORGE OPTIMAL PARAMS]
        </GlowButton>
      </TerminalSection>

      {/* Engine C: GA */}
      <TerminalSection title="ENGINE C: GENETIC ALGORITHM" accent="emerald" collapsible defaultOpen={false}>
        <div className="flex flex-col gap-2">
          <div className="text-caption text-text-secondary mb-1">Target Strategies (2+ for factor combo)</div>
          <div className="max-h-28 overflow-y-auto border border-border-dim p-2 flex flex-col gap-1">
            {STRATEGY_OPTIONS.map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer text-caption hover:text-text-primary transition-colors">
                <input type="checkbox" checked={gaStrategies.includes(s)}
                  onChange={e => toggleStrategy(gaStrategies, setGaStrategies, s, e.target.checked)}
                  className="accent-accent-emerald" />
                <span>{s}</span>
              </label>
            ))}
          </div>
          <NeonInput type="number" label="Population" value={gaPopulation} onChange={v => setGaPopulation(Number(v))} min={10} max={200} step={5} />
          <NeonInput type="number" label="Generations" value={gaGenerations} onChange={v => setGaGenerations(Number(v))} min={5} max={100} step={5} />
        </div>
        <GlowButton fullWidth onClick={() => handleRun("genetic", gaStrategies)}
          disabled={running || !connected || gaStrategies.length === 0} loading={running}>
          [EVOLVE OPTIMAL FACTORS]
        </GlowButton>
      </TerminalSection>
    </div>
  );
}
