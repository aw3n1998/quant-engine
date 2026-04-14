// frontend/src/types/index.ts

export interface StrategyInfo {
  id: string;
  name: string;
  description: string;
}

export interface EngineInfo {
  id: string;
  name: string;
  description: string;
}

export interface EngineResultData {
  engine: string;
  strategy: string;
  strategy_name: string;
  best_params: Record<string, number | string | Record<string, unknown>>;
  sharpe: number;
  calmar: number;
  max_drawdown: number;
  annual_return: number;
  alpha?: number;
  beta?: number;
  equity_curve: number[];
  extra_plots?: {
    history?: { data: unknown[]; layout: unknown };
    importance?: { data: unknown[]; layout: unknown };
    factor_weights?: Record<string, number>;
    convergence?: Array<{
      gen: number;
      strategy: string;
      best_calmar: number;
      std_calmar: number;
      phase: number;
    }>;
  };
  weight_history?: number[][];    // DRL/GA: [[w1,w2,...] per timestep]
  strategy_names?: string[];      // DRL/GA: strategy names for weight chart
  validation?: boolean;           // true = OOS 样本外验证结果
  source_run_id?: string;         // 来源 run 的 ID（validation=true 时）
}

export interface RunRequest {
  engine: string;
  strategies: string[];
  quick_mode: boolean;
  data_rows: number;
  oos_split: number;
  timeframe: string;
  target_roi: number;
  max_drawdown: number;
  friction_penalty: number;
  ppo_timesteps: number;
  optuna_trials: number;
  wfv_folds: number;
  ga_population: number;
  ga_generations: number;
}

export interface BinanceFetchRequest {
  symbol: string;
  timeframe: string;
  limit: number;
  use_mev?: boolean;
  use_nlp?: boolean;
  worldnews_api_key?: string;
}
export interface BatchRunRequest {
  engines: string[];
  strategy_groups: string[][];
  timeframes: string[];
  quick_mode: boolean;
  data_rows: number;
  oos_split: number;
  target_roi: number;
  max_drawdown: number;
  friction_penalty: number;
  ppo_timesteps: number;
  optuna_trials: number;
  wfv_folds: number;
  ga_population: number;
  ga_generations: number;
}

export type RunStatus = 'idle' | 'running' | 'complete' | 'error';

export interface LogMessage {
  type: 'log';
  level: 'info' | 'error' | 'warning';
  message: string;
  timestamp?: string;
}

export interface RunHistoryItem {
  run_id: string;
  timestamp: string;
  engine: string;
  strategies: string[];
  data_source: string;
  timeframe: string;
  sharpe: number;
  calmar: number;
  max_drawdown: number;
  annual_return: number;
  batch_id?: string;
}

export interface ProgressMessage {
  type: 'progress';
  engine: string;
  strategy: string;
  progress: number;
  message: string;
}

export interface ResultMessage {
  type: 'result';
  data: EngineResultData;
}

export interface BatchProgressMessage {
  type: 'batch_progress';
  progress: string;
  message: string;
}

export interface BatchSummaryMessage {
  type: 'batch_summary';
  data: EngineResultData;
}

export type WSMessage = LogMessage | ProgressMessage | ResultMessage | BatchProgressMessage | BatchSummaryMessage;
