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

export type WSMessage = LogMessage | ProgressMessage | ResultMessage;
