import { useState, useRef } from "react";
import { runEngine, uploadData } from "../services/api";
import type { RunStatus } from "../types";
import BinanceFetcher from "./BinanceFetcher";

const STRATEGY_OPTIONS = [
  "fibonacci_resonance", "mad_trend", "funding_arbitrage",
  "po3_institutional", "orderflow_imbalance", "mev_capture",
  "statistical_pair", "nlp_event_driven", "dynamic_market_making",
  "liquidation_hunting", "liquidity_hedge_mining", "macro_capital_flow",
];

const TIMEFRAMES = [
  { value: "1d",  label: "1D  日线（中长期）" },
  { value: "4h",  label: "4H  四小时（摆动）" },
  { value: "1h",  label: "1H  小时（日内推荐）" },
  { value: "30m", label: "30M 半小时" },
  { value: "15m", label: "15M 十五分钟" },
  { value: "5m",  label: "5M  五分钟（高频日内）" },
];

type DataSource = "synthetic" | "csv" | "binance";

interface Props {
  connected: boolean;
  runStatus: RunStatus;
}

export default function ControlPanel({ connected, runStatus }: Props) {
  const running = runStatus === 'running';
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 数据源
  const [dataSource, setDataSource] = useState<DataSource>("synthetic");
  const [dataRows, setDataRows] = useState(2000);
  const [dataInfo, setDataInfo] = useState<string | null>(null);

  // 全局
  const [oosSplit, setOosSplit] = useState(20);
  const [timeframe, setTimeframe] = useState("1d");

  // DRL
  const [targetRoi, setTargetRoi] = useState(10.0);
  const [maxDrawdown, setMaxDrawdown] = useState(-15.0);
  const [frictionPenalty, setFrictionPenalty] = useState(0.0005);
  const [ppoTimesteps, setPpoTimesteps] = useState(50000);

  // Bayesian
  const [optunaTrials, setOptunaTrials] = useState(80);
  const [wfvFolds, setWfvFolds] = useState(5);
  const [bayesianStrategies, setBayesianStrategies] = useState(["fibonacci_resonance"]);

  // GA
  const [gaStrategies, setGaStrategies] = useState(["fibonacci_resonance", "mad_trend"]);
  const [gaPopulation, setGaPopulation] = useState(40);
  const [gaGenerations, setGaGenerations] = useState(25);

  const buildCommonParams = () => ({
    quick_mode: false,
    data_rows: dataRows,
    oos_split: oosSplit,
    timeframe,
    target_roi: targetRoi,
    max_drawdown: maxDrawdown,
    friction_penalty: frictionPenalty,
    ppo_timesteps: ppoTimesteps,
    optuna_trials: optunaTrials,
    wfv_folds: wfvFolds,
    ga_population: gaPopulation,
    ga_generations: gaGenerations,
  });

  const handleRun = async (engine: string, strategies: string[]) => {
    if (strategies.length === 0) return;
    try {
      await runEngine({ engine, strategies, ...buildCommonParams() });
    } catch (err) {
      console.error(err);
    }
  };

  const handleCSVUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await uploadData(file);
      setDataInfo(`CSV: ${res.rows} 行`);
    } catch (err: unknown) {
      alert(`上传失败: ${err instanceof Error ? err.message : err}`);
    }
  };

  const toggleStrategy = (
    list: string[],
    setter: React.Dispatch<React.SetStateAction<string[]>>,
    sid: string,
    checked: boolean,
  ) => {
    setter(checked ? [...list, sid] : list.filter(x => x !== sid));
  };

  return (
    <div className="flex flex-col gap-5 text-sm">

      {/* ── 数据源 ────────────────────────────────────────────── */}
      <section>
        <h3 className="uppercase font-bold mb-3 border-b border-[#008F11]/50 pb-1 text-[#00FFFF]">
          [DATA SOURCE]
        </h3>
        <div className="flex gap-3 mb-3 text-xs">
          {(["synthetic", "csv", "binance"] as DataSource[]).map(ds => (
            <label key={ds} className="flex items-center gap-1 cursor-pointer">
              <input
                type="radio"
                name="datasource"
                value={ds}
                checked={dataSource === ds}
                onChange={() => setDataSource(ds)}
                className="accent-[#00FF41]"
              />
              <span className={dataSource === ds ? "text-[#00FF41]" : "text-[#008F11]"}>
                {ds === "synthetic" ? "合成" : ds === "csv" ? "CSV" : "Binance"}
              </span>
            </label>
          ))}
        </div>

        {dataSource === "synthetic" && (
          <label className="flex justify-between items-center text-xs">
            <span>K线数量</span>
            <input
              type="number" step={500} min={500} max={20000}
              className="matrix-input w-24"
              value={dataRows}
              onChange={e => setDataRows(Number(e.target.value))}
            />
          </label>
        )}

        {dataSource === "csv" && (
          <div className="flex flex-col gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={handleCSVUpload}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="matrix-btn py-1 text-xs"
            >
              [上传 CSV 文件]
            </button>
            {dataInfo && <div className="text-xs text-[#00FF41]">✓ {dataInfo}</div>}
          </div>
        )}

        {dataSource === "binance" && (
          <BinanceFetcher
            onLoaded={info => setDataInfo(`${info.symbol} ${info.timeframe} × ${info.rows}根`)}
          />
        )}
      </section>

      {/* ── 全局参数 ─────────────────────────────────────────── */}
      <section>
        <h3 className="uppercase font-bold mb-3 border-b border-[#008F11]/50 pb-1 text-[#00FFFF]">
          [GLOBAL SETTINGS]
        </h3>
        <div className="flex flex-col gap-3 text-xs">
          <label className="flex flex-col gap-1">
            <span>时间框架（影响年化因子与WFV窗口）</span>
            <select
              className="matrix-input w-full bg-[#050a05]"
              value={timeframe}
              onChange={e => setTimeframe(e.target.value)}
            >
              {TIMEFRAMES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span>OOS 测试切分 ({oosSplit}%)</span>
            <input
              type="range" min={5} max={50}
              value={oosSplit}
              onChange={e => setOosSplit(Number(e.target.value))}
            />
          </label>
        </div>
      </section>

      {/* ── Engine A: DRL ────────────────────────────────────── */}
      <section>
        <h3 className="uppercase font-bold mb-3 border-b border-[#008F11]/50 pb-1 text-[#C724FF]">
          [ENGINE A: DRL PIPELINE]
        </h3>
        <div className="flex flex-col gap-2 text-xs">
          <label className="flex justify-between">Target ROI %
            <input type="number" step="0.1" className="matrix-input w-20" value={targetRoi} onChange={e => setTargetRoi(Number(e.target.value))} />
          </label>
          <label className="flex justify-between">Max Drawdown %
            <input type="number" step="0.1" className="matrix-input w-20" value={maxDrawdown} onChange={e => setMaxDrawdown(Number(e.target.value))} />
          </label>
          <label className="flex justify-between">Friction Penalty
            <input type="number" step="0.0001" className="matrix-input w-20" value={frictionPenalty} onChange={e => setFrictionPenalty(Number(e.target.value))} />
          </label>
          <label className="flex justify-between">PPO Timesteps
            <input type="number" step="1000" className="matrix-input w-20" value={ppoTimesteps} onChange={e => setPpoTimesteps(Number(e.target.value))} />
          </label>
        </div>
        <button
          onClick={() => handleRun("drl", STRATEGY_OPTIONS)}
          disabled={running || !connected}
          className="matrix-btn mt-3 py-2 w-full"
        >
          [INITIATE PPO FUSION]
        </button>
      </section>

      {/* ── Engine B: Bayesian ───────────────────────────────── */}
      <section>
        <h3 className="uppercase font-bold mb-3 border-b border-[#008F11]/50 pb-1 text-[#00FFFF]">
          [ENGINE B: BAYESIAN PIPELINE]
        </h3>
        <div className="flex flex-col gap-2 text-xs">
          <div className="flex flex-col gap-1">
            <span className="text-[#008F11]">Target Strategies</span>
            <div className="max-h-28 overflow-y-auto border border-[#008F11]/30 p-2 flex flex-col gap-1">
              {STRATEGY_OPTIONS.map(s => (
                <label key={s} className="flex items-center gap-2 cursor-pointer hover:text-[#00FF41]">
                  <input
                    type="checkbox"
                    checked={bayesianStrategies.includes(s)}
                    onChange={e => toggleStrategy(bayesianStrategies, setBayesianStrategies, s, e.target.checked)}
                    className="accent-[#00FF41]"
                  />
                  <span>{s}</span>
                </label>
              ))}
            </div>
          </div>
          <label className="flex justify-between">Optuna Trials
            <input type="number" step="10" className="matrix-input w-20" value={optunaTrials} onChange={e => setOptunaTrials(Number(e.target.value))} />
          </label>
          <label className="flex justify-between">WFV Folds
            <input type="number" step="1" min="2" max="10" className="matrix-input w-20" value={wfvFolds} onChange={e => setWfvFolds(Number(e.target.value))} />
          </label>
        </div>
        <button
          onClick={() => handleRun("bayesian", bayesianStrategies)}
          disabled={running || !connected || bayesianStrategies.length === 0}
          className="matrix-btn mt-3 py-2 w-full"
        >
          [FORGE OPTIMAL PARAMS]
        </button>
      </section>

      {/* ── Engine C: Genetic Algorithm ──────────────────────── */}
      <section>
        <h3 className="uppercase font-bold mb-3 border-b border-[#008F11]/50 pb-1 text-[#00FF41]">
          [ENGINE C: GENETIC ALGORITHM]
        </h3>
        <div className="flex flex-col gap-2 text-xs">
          <div className="flex flex-col gap-1">
            <span className="text-[#008F11]">Target Strategies (≥2 启用因子组合)</span>
            <div className="max-h-28 overflow-y-auto border border-[#008F11]/30 p-2 flex flex-col gap-1">
              {STRATEGY_OPTIONS.map(s => (
                <label key={s} className="flex items-center gap-2 cursor-pointer hover:text-[#00FF41]">
                  <input
                    type="checkbox"
                    checked={gaStrategies.includes(s)}
                    onChange={e => toggleStrategy(gaStrategies, setGaStrategies, s, e.target.checked)}
                    className="accent-[#00FF41]"
                  />
                  <span>{s}</span>
                </label>
              ))}
            </div>
          </div>
          <label className="flex justify-between">Population Size
            <input type="number" step="5" min="10" max="200" className="matrix-input w-20" value={gaPopulation} onChange={e => setGaPopulation(Number(e.target.value))} />
          </label>
          <label className="flex justify-between">Generations
            <input type="number" step="5" min="5" max="100" className="matrix-input w-20" value={gaGenerations} onChange={e => setGaGenerations(Number(e.target.value))} />
          </label>
        </div>
        <button
          onClick={() => handleRun("genetic", gaStrategies)}
          disabled={running || !connected || gaStrategies.length === 0}
          className="matrix-btn mt-3 py-2 w-full"
          style={{ borderColor: '#00FF41', color: '#00FF41' }}
        >
          [EVOLVE OPTIMAL FACTORS]
        </button>
      </section>

    </div>
  );
}
