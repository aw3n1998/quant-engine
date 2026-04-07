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
  best_params: Record<string, number | string>;
  sharpe: number;
  calmar: number;
  max_drawdown: number;
  annual_return: number;
  equity_curve: number[];
  extra_plots?: any;
}

export interface RunRequest {
  engine: string;
  strategies: string[];
  quick_mode: boolean;
  data_rows: number;
  oos_split: number;
  target_roi: number;
  max_drawdown: number;
  friction_penalty: number;
  ppo_timesteps: number;
  optuna_trials: number;
  wfv_folds: number;
}

export interface LogMessage {
  type: "log";
  level: "info" | "error" | "warning";
  message: string;
  timestamp?: string;
}

export interface ProgressMessage {
  type: "progress";
  engine: string;
  strategy: string;
  progress: number;
  message: string;
}

export interface ResultMessage {
  type: "result";
  data: EngineResultData;
}

export type WSMessage = LogMessage | ProgressMessage | ResultMessage;
