import { useState, useRef } from "react";
import { runEngine, uploadData } from "../services/api";
import type { RunStatus, EngineResultData } from "../types";
import BinanceFetcher from "./BinanceFetcher";
import TerminalSection from "./ui/TerminalSection";
import GlowButton from "./ui/GlowButton";
import NeonInput from "./ui/NeonInput";
import { STRATEGY_META } from "../data/glossary";
import BatchMatrixModal from "./BatchMatrixModal";

const STRATEGY_OPTIONS = [
  // 保留策略
  "fibonacci_resonance", "mad_trend", "po3_institutional",
  "orderflow_imbalance", "mev_capture", "nlp_event_driven",
  "liquidation_hunting",
  // 纯K线高回报策略
  "donchian_breakout", "bollinger_squeeze", "ema_trend_filter",
  "rsi_momentum", "volume_price_momentum",
  // 高级策略（自适应 / ML / 价格行为）
  "regime_meta", "ml_feature_sr", "price_action_sr",
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
  batchProgress: string;
  batchResults: EngineResultData[];
}

export default function ControlPanel({ connected, runStatus, batchProgress, batchResults }: Props) {
  const running = runStatus === 'running';
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource>("synthetic");
  const [dataRows, setDataRows] = useState(2000);
  const [dataInfo, setDataInfo] = useState<string | null>(null);
  const [csvTimeframe, setCsvTimeframe] = useState("1h");
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
  const [ensembleStrategies, setEnsembleStrategies] = useState(["rsi_momentum", "bollinger_squeeze", "mad_trend"]);
  const [gaPopulation, setGaPopulation] = useState(40);
  const [gaGenerations, setGaGenerations] = useState(25);
  const [expertMode, setExpertMode] = useState(false);

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
      const res = await uploadData(file, csvTimeframe);
      setDataInfo(`CSV: ${res.rows} rows [${res.timeframe}]`);
      setTimeframe(csvTimeframe);  // 同步全局时间框架
    } catch (err: unknown) {
      alert(`Upload failed: ${err instanceof Error ? err.message : err}`);
    }
  };

  const toggleStrategy = (list: string[], setter: React.Dispatch<React.SetStateAction<string[]>>, sid: string, checked: boolean) => {
    setter(checked ? [...list, sid] : list.filter(x => x !== sid));
  };

  return (
    <div className="flex flex-col gap-3">
      {/* Presets + Expert mode toggle */}
      <div className="flex gap-2 flex-wrap items-center">
        {([
          ['quick',    '快速测试'],
          ['standard', '标准'],
          ['deep',     '深度'],
        ] as [keyof typeof PRESETS, string][]).map(([k, label]) => (
          <span key={k} title={`预设：${label}`}>
            <GlowButton size="sm" onClick={() => applyPreset(k)}>
              {k.toUpperCase()}
            </GlowButton>
          </span>
        ))}
        <label className="ml-auto flex items-center gap-1 cursor-pointer text-caption text-text-muted select-none">
          <input
            type="checkbox"
            checked={expertMode}
            onChange={e => setExpertMode(e.target.checked)}
            className="accent-accent-emerald"
          />
          专家模式
        </label>
      </div>

      <div className="flex">
        <GlowButton fullWidth size="sm" onClick={() => setBatchModalOpen(true)}>
          [OPEN BATCH RUNNER MATRIX]
        </GlowButton>
      </div>

      {batchModalOpen && (
        <BatchMatrixModal 
          onClose={() => setBatchModalOpen(false)}
          baseParams={buildCommonParams()}
          batchProgress={batchProgress}
          batchResults={batchResults}
        />
      )}

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
            <NeonInput type="select" label="Timeframe" value={csvTimeframe} onChange={setCsvTimeframe} layout="col"
              options={TIMEFRAMES} />
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
      <TerminalSection
        title={<span className="flex items-center gap-1">ENGINE A: DRL <span className="text-[9px] px-1 py-0.5 border border-accent-amber text-accent-amber leading-none">推荐</span></span>}
        accent="magenta" collapsible defaultOpen={false}
      >
        <div className="text-caption text-text-muted mb-2">深度强化学习 — AI 自主学习最优仓位，适合新手，无需调参</div>
        <div className="flex flex-col gap-2">
          <NeonInput type="number" label="Target ROI %" value={targetRoi} onChange={v => setTargetRoi(Number(v))} step={0.1}
            tooltip="收益目标（%）：达到后提前终止训练并给予奖励。10 = 10% 收益时停止并+1奖励" />
          <NeonInput type="number" label="Max DD %" value={maxDrawdown} onChange={v => setMaxDrawdown(Number(v))} step={0.1}
            tooltip="最大回撤止损（负值）：-15 表示亏损超过 15% 时触发强制平仓并-1惩罚" />
          <NeonInput type="number" label="Friction" value={frictionPenalty} onChange={v => setFrictionPenalty(Number(v))} step={0.0001}
            tooltip="调仓摩擦成本：0.0005 = 每次再平衡扣 0.05%，防止 PPO 过度频繁换仓" />
          {expertMode && (
            <NeonInput type="number" label="PPO Steps" value={ppoTimesteps} onChange={v => setPpoTimesteps(Number(v))} step={1000}
              tooltip="PPO 总训练步数（分配到各 WFV 折）。1步 = 1根K线的虚拟交易。建议：日线≥50K，1H≥200K" />
          )}
        </div>
        <GlowButton fullWidth onClick={() => handleRun("drl", STRATEGY_OPTIONS)} disabled={running || !connected} loading={running}>
          [INITIATE PPO FUSION]
        </GlowButton>
      </TerminalSection>

      {/* Engine B: Bayesian */}
      <TerminalSection title="ENGINE B: BAYESIAN" accent="cyan" collapsible defaultOpen={false}>
        <div className="text-caption text-text-muted mb-2">贝叶斯优化 — 智能搜索最优策略参数，适合有策略偏好的用户</div>
        <div className="flex flex-col gap-2">
          <div className="text-caption text-text-secondary mb-1">Target Strategies</div>
          <div className="max-h-28 overflow-y-auto border border-border-dim p-2 flex flex-col gap-1">
            {STRATEGY_OPTIONS.map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer text-caption hover:text-text-primary transition-colors"
                title={STRATEGY_META[s]?.desc}>
                <input type="checkbox" checked={bayesianStrategies.includes(s)}
                  onChange={e => toggleStrategy(bayesianStrategies, setBayesianStrategies, s, e.target.checked)}
                  className="accent-accent-emerald" />
                <span>{STRATEGY_META[s]?.name ?? s}</span>
              </label>
            ))}
          </div>
          <NeonInput type="number" label="Trials" value={optunaTrials} onChange={v => setOptunaTrials(Number(v))} step={10}
            tooltip="Optuna 优化试验次数。更多=结果更优但更慢。建议：快速测试 20，正式运行 80-200" />
          {expertMode && (
            <NeonInput type="number" label="WFV Folds" value={wfvFolds} onChange={v => setWfvFolds(Number(v))} min={2} max={10} step={1}
              tooltip="Walk-Forward 滚动折数：每折在独立时段验证参数。更多折=更稳健但更慢。DRL上限3折" />
          )}
        </div>
        <GlowButton fullWidth onClick={() => handleRun("bayesian", bayesianStrategies)}
          disabled={running || !connected || bayesianStrategies.length === 0} loading={running}>
          [FORGE OPTIMAL PARAMS]
        </GlowButton>
      </TerminalSection>

      {/* Engine C: GA */}
      <TerminalSection title="ENGINE C: GENETIC ALGORITHM" accent="emerald" collapsible defaultOpen={false}>
        <div className="text-caption text-text-muted mb-2">遗传算法 — 进化组合多策略权重，适合追求极致优化的用户</div>
        <div className="flex flex-col gap-2">
          <div className="text-caption text-text-secondary mb-1">Target Strategies (2+ for factor combo)</div>
          <div className="max-h-28 overflow-y-auto border border-border-dim p-2 flex flex-col gap-1">
            {STRATEGY_OPTIONS.map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer text-caption hover:text-text-primary transition-colors"
                title={STRATEGY_META[s]?.desc}>
                <input type="checkbox" checked={gaStrategies.includes(s)}
                  onChange={e => toggleStrategy(gaStrategies, setGaStrategies, s, e.target.checked)}
                  className="accent-accent-emerald" />
                <span>{STRATEGY_META[s]?.name ?? s}</span>
              </label>
            ))}
          </div>
          <NeonInput type="number" label="Population" value={gaPopulation} onChange={v => setGaPopulation(Number(v))} min={10} max={200} step={5}
            tooltip="每代种群大小。更大=搜索空间更广但更慢。建议：快速 15，标准 40，深度 60" />
          <NeonInput type="number" label="Generations" value={gaGenerations} onChange={v => setGaGenerations(Number(v))} min={5} max={100} step={5}
            tooltip="GA 进化代数。每代淘汰劣解，保留精英。建议：快速 8，标准 25，深度 50" />
        </div>
        <GlowButton fullWidth onClick={() => handleRun("genetic", gaStrategies)}
          disabled={running || !connected || gaStrategies.length === 0} loading={running}>
          [EVOLVE OPTIMAL FACTORS]
        </GlowButton>
      </TerminalSection>

      {/* Engine D: Bandit */}
      <TerminalSection title="ENGINE D: BANDIT" accent="cyan" collapsible defaultOpen={false}>
        <div className="text-caption text-text-muted mb-2">Thompson Sampling — 在线学习，每根K线实时更新策略权重，自动平衡探索与利用</div>
        <GlowButton fullWidth onClick={() => handleRun("bandit", STRATEGY_OPTIONS)} disabled={running || !connected} loading={running}>
          [EXPLORE &amp; EXPLOIT]
        </GlowButton>
      </TerminalSection>

      {/* Engine E: Volatility */}
      <TerminalSection title="ENGINE E: VOLATILITY" accent="emerald" collapsible defaultOpen={false}>
        <div className="text-caption text-text-muted mb-2">波动率自适应 — 按市场波动率分3档，高波动切防御权重，低波动切高收益权重</div>
        <GlowButton fullWidth onClick={() => handleRun("volatility", STRATEGY_OPTIONS)} disabled={running || !connected} loading={running}>
          [ADAPT TO VOLATILITY]
        </GlowButton>
      </TerminalSection>

      {/* Engine F: Ensemble */}
      <TerminalSection title="ENGINE F: ENSEMBLE" accent="magenta" collapsible defaultOpen={false}>
        <div className="text-caption text-text-muted mb-2">集成学习 — 各子策略独立 Bayesian 优化，IS Sharpe 作为专家权重，加权信号融合</div>
        <div className="flex flex-col gap-2">
          <div className="text-caption text-text-secondary mb-1">Target Strategies</div>
          <div className="max-h-28 overflow-y-auto border border-border-dim p-2 flex flex-col gap-1">
            {STRATEGY_OPTIONS.map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer text-caption hover:text-text-primary transition-colors"
                title={STRATEGY_META[s]?.desc}>
                <input type="checkbox" checked={ensembleStrategies.includes(s)}
                  onChange={e => toggleStrategy(ensembleStrategies, setEnsembleStrategies, s, e.target.checked)}
                  className="accent-accent-emerald" />
                <span>{STRATEGY_META[s]?.name ?? s}</span>
              </label>
            ))}
          </div>
        </div>
        <GlowButton fullWidth onClick={() => handleRun("ensemble", ensembleStrategies)}
          disabled={running || !connected || ensembleStrategies.length === 0} loading={running}>
          [FUSE EXPERT SIGNALS]
        </GlowButton>
      </TerminalSection>

      {/* Engine G: Monte Carlo */}
      <TerminalSection title="ENGINE G: MONTE CARLO" accent="cyan" collapsible defaultOpen={false}>
        <div className="text-caption text-text-muted mb-2">蒙特卡洛鲁棒性 — 参数扰动 N 次采样，报告 Sharpe 分布 P5/中位数，识别过拟合风险</div>
        <GlowButton fullWidth onClick={() => handleRun("montecarlo", STRATEGY_OPTIONS)} disabled={running || !connected} loading={running}>
          [TEST ROBUSTNESS]
        </GlowButton>
      </TerminalSection>

      {/* Engine H: Risk Parity */}
      <TerminalSection title="ENGINE H: RISK PARITY" accent="emerald" collapsible defaultOpen={false}>
        <div className="text-caption text-text-muted mb-2">风险平价 — 按策略信号波动率倒数分配权重，高波动策略自动降权，追求等风险贡献</div>
        <GlowButton fullWidth onClick={() => handleRun("risk_parity", STRATEGY_OPTIONS)} disabled={running || !connected} loading={running}>
          [BALANCE RISK]
        </GlowButton>
      </TerminalSection>
    </div>
  );
}
