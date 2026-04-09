# backend/app/engines/ensemble_engine.py
"""
Ensemble Engine（集成学习引擎）

核心方法: 多专家加权投票（Expert Weighting）

工作流程:
    1. 对每个策略在 IS 数据上用 Optuna 独立寻优最优参数
    2. 用各策略的 IS Sharpe 作为专家权重（Sharpe 越高权重越大）
    3. OOS 阶段按加权平均合并所有策略信号
    4. 负 Sharpe 策略权重归零（排除劣质专家）

与 GA 的区别:
    - GA 进化权重系数（黑箱搜索）
    - Ensemble 用 IS Sharpe 直接计算权重（透明、可解释、更快）

优势:
    - 每个策略独立优化，充分发挥各自优势
    - 权重直接来自 IS 绩效，无需额外优化步骤
    - 结果高度可解释（知道每个专家贡献多少）
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import optuna

optuna.logging.set_verbosity(optuna.logging.WARNING)

from app.core.base_engine import BaseEngine, EngineResult
from app.core.base_strategy import BaseStrategy
from app.core.engine_registry import ENGINE_REGISTRY
from app.utils.metrics import compute_all_metrics, sharpe_ratio

logger = logging.getLogger("quant_engine.ensemble")


class EnsembleEngine(BaseEngine):
    def __init__(self) -> None:
        super().__init__(
            name="Ensemble (Expert Weighting)",
            description="Each strategy independently optimized via Bayesian search; IS Sharpe used as expert weight",
        )

    def run(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        log_callback=None,
        **kwargs,
    ) -> EngineResult:
        def emit(msg: str, level: str = "info") -> None:
            if log_callback:
                log_callback(level, msg)

        strategies: list[BaseStrategy] = kwargs.get("strategies", [strategy])
        timeframe: str   = kwargs.get("timeframe", "1d")
        oos_split: float = kwargs.get("oos_split", 20.0)
        n_trials: int    = kwargs.get("optuna_trials", 40)

        n = len(strategies)
        emit(f"[Ensemble] 初始化 | {n} 个策略 | {n_trials} 次 Optuna 试验/策略")

        # 划分 IS / OOS
        split_idx = int(len(df) * (1 - oos_split / 100))
        df_is  = df.iloc[:split_idx].reset_index(drop=True)
        df_oos = df.iloc[split_idx:].reset_index(drop=True)

        if len(df_is) < 80:
            emit("[Ensemble] IS 数据不足，返回空结果", "warning")
            return EngineResult()

        # ─── 为每个策略独立做 Bayesian 优化 ───
        best_params_per_strategy: list[dict] = []
        is_sharpe_per_strategy: list[float]  = []
        strategy_names: list[str] = []

        for idx, s in enumerate(strategies):
            emit(f"[Ensemble] 优化策略 {idx+1}/{n}: {s.name}")

            def objective(trial):
                try:
                    params = s.get_param_space(trial)
                    sig = s.generate_signals(df_is, params)
                    return sharpe_ratio(sig, timeframe=timeframe)
                except Exception:
                    return -999.0

            study = optuna.create_study(direction="maximize")
            study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

            best_p = study.best_params
            best_sharpe = max(study.best_value, 0.0)  # 负 Sharpe → 权重 0

            best_params_per_strategy.append(best_p)
            is_sharpe_per_strategy.append(best_sharpe)
            strategy_names.append(s.name)

            emit(f"[Ensemble]   {s.name} IS Sharpe={study.best_value:.3f} → 权重分子={best_sharpe:.3f}")

        # ─── 计算专家权重（softmax over IS Sharpe，负值归零）───
        sharpe_arr = np.array(is_sharpe_per_strategy, dtype=float)
        if sharpe_arr.sum() < 1e-9:
            # 全部劣质策略 → 等权
            weights = np.ones(n) / n
            emit("[Ensemble] 所有策略 IS Sharpe ≤ 0，降级为等权", "warning")
        else:
            weights = sharpe_arr / sharpe_arr.sum()

        emit(f"[Ensemble] 专家权重: {dict(zip(strategy_names, [round(w, 4) for w in weights]))}")

        # ─── OOS 加权合并 ───
        oos_combined = pd.Series(0.0, index=df_oos.index)
        weight_history: list[list[float]] = [[float(w) for w in weights]] * len(df_oos)

        for i, s in enumerate(strategies):
            if weights[i] < 1e-9:
                continue
            try:
                sig_oos = s.generate_signals(df_oos, best_params_per_strategy[i])
            except Exception:
                sig_oos = pd.Series(0.0, index=df_oos.index)
            oos_combined += weights[i] * sig_oos

        metrics = compute_all_metrics(oos_combined, timeframe=timeframe)

        best_params_out = {}
        for i, s in enumerate(strategies):
            best_params_out[f"weight_{s.name}"] = round(float(weights[i]), 4)
            for k, v in best_params_per_strategy[i].items():
                best_params_out[f"{s.name}.{k}"] = v

        emit(f"[Ensemble] OOS Sharpe={metrics['sharpe']:.3f} | Calmar={metrics['calmar']:.3f}")

        return EngineResult(
            best_params=best_params_out,
            sharpe=metrics["sharpe"],
            calmar=metrics["calmar"],
            max_drawdown=metrics["max_drawdown"],
            annual_return=metrics["annual_return"],
            equity_curve=metrics["equity_curve"],
            weight_history=weight_history,
            strategy_names=strategy_names,
        )


ENGINE_REGISTRY.register("ensemble", EnsembleEngine)
