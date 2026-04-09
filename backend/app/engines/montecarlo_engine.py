# backend/app/engines/montecarlo_engine.py
"""
Monte Carlo Engine（蒙特卡洛鲁棒性引擎）

核心方法: 参数扰动 + Sharpe 分布估计

工作流程:
    1. 用 Optuna 在 IS 数据上找到最优参数（基准参数）
    2. 在基准参数附近做 N 次随机扰动（±扰动幅度内均匀采样）
    3. 对每组扰动参数运行完整 IS 回测，收集 Sharpe 序列
    4. 报告 Sharpe 分布统计：中位数、5%分位数（鲁棒性下界）、标准差
    5. OOS 阶段用中位数参数运行

核心价值:
    - 衡量策略对参数的敏感性（Sharpe std 低 = 鲁棒，高 = 过拟合）
    - sharpe_p5 是比 IS Sharpe 更保守的预期下界
    - 帮助识别参数窗口（parameter cliff edge）问题

额外输出字段（在 best_params 中）:
    - sharpe_p5      (5% 分位 Sharpe，鲁棒性下界)
    - sharpe_median  (中位 Sharpe)
    - sharpe_std     (Sharpe 波动率，越低越鲁棒)
    - mc_trials      (实际完成的 MC 次数)
"""
from __future__ import annotations

import logging
import random

import numpy as np
import pandas as pd
import optuna

optuna.logging.set_verbosity(optuna.logging.WARNING)

from app.core.base_engine import BaseEngine, EngineResult
from app.core.base_strategy import BaseStrategy
from app.core.engine_registry import ENGINE_REGISTRY
from app.utils.metrics import compute_all_metrics, sharpe_ratio

logger = logging.getLogger("quant_engine.montecarlo")


class _FakeTrial:
    """返回参数中值以获取默认参数"""
    def suggest_int(self, name: str, low: int, high: int, **kw) -> int:
        return (low + high) // 2

    def suggest_float(self, name: str, low: float, high: float, **kw) -> float:
        return (low + high) / 2


class MonteCarloEngine(BaseEngine):
    def __init__(self) -> None:
        super().__init__(
            name="Monte Carlo Robustness",
            description="Parameter perturbation N times; reports Sharpe distribution P5/median/std to measure robustness",
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
        timeframe: str    = kwargs.get("timeframe", "1d")
        oos_split: float  = kwargs.get("oos_split", 20.0)
        n_trials: int     = kwargs.get("optuna_trials", 30)
        mc_samples: int   = kwargs.get("mc_samples", 50)  # MC 扰动次数
        perturb: float    = 0.20                           # 参数扰动幅度 ±20%

        # 仅对第一个策略做 MC 分析（多策略时分别分析，取平均）
        # 若只传一个策略则直接分析
        strategy_names = [s.name for s in strategies]
        n = len(strategies)

        emit(f"[MonteCarlo] 初始化 | {n} 个策略 | Optuna={n_trials} | MC={mc_samples}")

        # 划分 IS / OOS
        split_idx = int(len(df) * (1 - oos_split / 100))
        df_is  = df.iloc[:split_idx].reset_index(drop=True)
        df_oos = df.iloc[split_idx:].reset_index(drop=True)

        if len(df_is) < 80:
            emit("[MonteCarlo] IS 数据不足", "warning")
            return EngineResult()

        all_best_params: list[dict] = []
        all_mc_sharpes: list[list[float]] = []

        for idx, s in enumerate(strategies):
            emit(f"[MonteCarlo] Step1 Optuna 优化: {s.name}")

            # Step 1: 找基准参数
            def objective(trial):
                try:
                    params = s.get_param_space(trial)
                    sig = s.generate_signals(df_is, params)
                    return sharpe_ratio(sig, timeframe=timeframe)
                except Exception:
                    return -999.0

            study = optuna.create_study(direction="maximize")
            study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
            base_params = study.best_params
            all_best_params.append(base_params)

            emit(f"[MonteCarlo]   {s.name} 基准 Sharpe={study.best_value:.3f} | 开始 {mc_samples} 次 MC 扰动...")

            # Step 2: MC 扰动采样
            mc_sharpes: list[float] = []
            rng = random.Random(42)

            for mc_i in range(mc_samples):
                # 在基准参数附近扰动
                perturbed = {}
                for k, v in base_params.items():
                    if isinstance(v, int):
                        delta = max(1, int(abs(v) * perturb))
                        perturbed[k] = max(1, v + rng.randint(-delta, delta))
                    elif isinstance(v, float):
                        delta = abs(v) * perturb
                        perturbed[k] = v + rng.uniform(-delta, delta)
                    else:
                        perturbed[k] = v

                try:
                    sig = s.generate_signals(df_is, perturbed)
                    sh = sharpe_ratio(sig, timeframe=timeframe)
                    mc_sharpes.append(sh if np.isfinite(sh) else 0.0)
                except Exception:
                    mc_sharpes.append(0.0)

            all_mc_sharpes.append(mc_sharpes)
            arr = np.array(mc_sharpes)
            emit(
                f"[MonteCarlo]   {s.name} MC Sharpe: "
                f"P5={np.percentile(arr,5):.3f} "
                f"Med={np.median(arr):.3f} "
                f"Std={arr.std():.3f}"
            )

        # ─── OOS 评估：使用各策略最优参数，等权合并 ───
        oos_combined = pd.Series(0.0, index=df_oos.index)
        weight = 1.0 / n

        for i, s in enumerate(strategies):
            try:
                sig_oos = s.generate_signals(df_oos, all_best_params[i])
            except Exception:
                sig_oos = pd.Series(0.0, index=df_oos.index)
            oos_combined += weight * sig_oos

        metrics = compute_all_metrics(oos_combined, timeframe=timeframe)

        # 汇总 MC 统计（所有策略平均）
        combined_mc = np.concatenate(all_mc_sharpes)
        sharpe_p5     = float(np.percentile(combined_mc, 5))
        sharpe_median = float(np.median(combined_mc))
        sharpe_std    = float(np.std(combined_mc))

        best_params_out: dict = {
            "sharpe_p5":     round(sharpe_p5,     4),
            "sharpe_median": round(sharpe_median, 4),
            "sharpe_std":    round(sharpe_std,    4),
            "mc_trials":     len(combined_mc),
        }
        for i, s in enumerate(strategies):
            for k, v in all_best_params[i].items():
                best_params_out[f"{s.name}.{k}"] = v

        weight_history = [[weight] * n] * len(df_oos)

        emit(
            f"[MonteCarlo] OOS Sharpe={metrics['sharpe']:.3f} | "
            f"MC P5={sharpe_p5:.3f} Med={sharpe_median:.3f} Std={sharpe_std:.3f}"
        )

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


ENGINE_REGISTRY.register("montecarlo", MonteCarloEngine)
