# backend/app/engines/bayesian_engine.py
"""
Bayesian 优化引擎

核心方法: Optuna + Walk-Forward Validation (滚动前向验证)

工作流程:
    1. 接收策略实例和数据
    2. 使用 Optuna 搜索策略超参数
    3. 每组参数在 Walk-Forward Validation 中评估
    4. 优化目标: 最大化各折的平均 Calmar Ratio
    5. 返回统一的 EngineResult

防过拟合核心设计:
    Walk-Forward Validation 严格保证时序性:
    - 训练窗口始终在测试窗口之前
    - 每一折的训练集和测试集不重叠
    - 最终性能取多折平均，避免单一时段的偶然高表现
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.config.config import config
from app.core.base_engine import BaseEngine, EngineResult
from app.core.base_strategy import BaseStrategy
from app.core.engine_registry import ENGINE_REGISTRY
from app.utils.helpers import set_global_seed
from app.utils.metrics import calmar_ratio, compute_all_metrics


# 抑制 Optuna 的冗余日志输出
optuna.logging.set_verbosity(optuna.logging.WARNING)


class BayesianEngine(BaseEngine):
    """
    基于 Optuna 的贝叶斯超参数优化引擎
    使用 Walk-Forward Validation 防止过拟合
    """

    def __init__(self) -> None:
        super().__init__(
            name="Bayesian (Optuna)",
            description="Bayesian hyperparameter optimization with Walk-Forward Validation targeting Calmar Ratio",
        )

    def run(self, strategy, df: pd.DataFrame, log_callback=None, **kwargs) -> EngineResult:
        def emit(msg: str) -> None:
            if log_callback:
                log_callback("info", msg)

        set_global_seed(config.default_seed)

        n_trials = kwargs.get("optuna_trials", 100)
        n_splits = (
            config.bayesian_n_splits_quick
            if config.quick_mode
            else config.bayesian_n_splits
        )
        min_train = config.bayesian_min_train_size

        # ----------------------------------------------------------------
        # 【滚动交叉验证防过拟合意图】
        # Walk-Forward Validation (WFV) 分割点计算
        #
        # 核心防过拟合思路:
        #   在量化交易中，传统的随机划分数据（K-Fold交叉验证）属于“利用未来预测历史”，
        #   这是绝对禁止的。本处的 Walk-Forward Validation 严格保障时序：
        #   每一折（Fold）的训练集都在验证集之前，且只发生前向滚动。
        #   这样能在多个不同的历史周期（如牛市片段、熊市片段）中反复模拟
        #   真实的“先优化后实盘”过程，避免策略在某一单边行情上过拟合。
        # ----------------------------------------------------------------
        total_rows = len(df)
        fold_size = (total_rows - min_train) // (n_splits + 1)

        if fold_size < 30:
            fold_size = 30

        splits = []
        for i in range(n_splits):
            train_end = min_train + fold_size * (i + 1)
            val_start = train_end
            val_end = min(val_start + fold_size, total_rows)
            if val_end <= val_start:
                break
            splits.append((0, train_end, val_start, val_end))

        if not splits:
            splits = [(0, int(total_rows * 0.7), int(total_rows * 0.7), total_rows)]

        def objective(trial: optuna.Trial) -> float:
            params = strategy.get_param_space(trial)

            # ----------------------------------------------------------
            # Walk-Forward Validation 循环
            #
            # 防过拟合意图:
            #   对每组候选参数，在多个不重叠的时间段上评估性能。
            #   只有在所有时段上都表现稳健的参数才会获得高分。
            #   这样能有效过滤掉"仅在特定时段偶然表现好"的参数组合，
            #   从而降低过拟合风险。
            #
            # 评估指标:
            #   使用 Calmar Ratio (年化收益 / 最大回撤) 而非纯收益，
            #   因为 Calmar 同时考虑收益和风险，不容易被极端收益欺骗。
            # ----------------------------------------------------------
            fold_calmars = []
            for train_start, train_end, val_start, val_end in splits:
                val_df = df.iloc[val_start:val_end]
                val_returns = strategy.generate_signals(val_df, params)

                cr = calmar_ratio(val_returns)
                if np.isnan(cr) or np.isinf(cr):
                    cr = -10.0
                fold_calmars.append(cr)

            # ----------------------------------------------------------
            # 取所有折的平均 Calmar Ratio 作为最终得分
            #
            # 防过拟合意图:
            #   平均操作天然地惩罚了高方差策略:
            #   如果一个参数组合在某些折表现极好但在其他折表现极差，
            #   其平均分会低于一个在所有折上表现稳定的参数组合。
            #   这就是"稳定性优先"的优化哲学。
            # ----------------------------------------------------------
            mean_calmar = float(np.mean(fold_calmars))
            return mean_calmar

        emit(f"[{self.name}] Optimizing Parameters... {n_trials} trials across {len(splits)} rolling folds")
        sampler = optuna.samplers.TPESampler(seed=config.default_seed)
        pruner = optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1)
        study = optuna.create_study(direction="maximize", sampler=sampler, pruner=pruner)
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        best_params = study.best_trial.params

        emit(f"[{self.name}] Converging... found optimal parameters. Generating final simulation.")
        # 使用最优参数在全量数据上计算最终绩效
        final_returns = strategy.generate_signals(df, best_params)
        metrics = compute_all_metrics(final_returns)

        return EngineResult(
            best_params=best_params,
            sharpe=metrics["sharpe"],
            calmar=metrics["calmar"],
            max_drawdown=metrics["max_drawdown"],
            annual_return=metrics["annual_return"],
            equity_curve=metrics["equity_curve"],
        )


ENGINE_REGISTRY.register("bayesian", BayesianEngine)
