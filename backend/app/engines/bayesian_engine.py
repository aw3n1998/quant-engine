# backend/app/engines/bayesian_engine.py
"""
Bayesian 优化引擎（万能模块化 Optuna Pipeline）

核心方法: Optuna TPE + Walk-Forward Validation + 因子权重元优化

工作流程:
    1. 对每个选中策略独立运行 Optuna 优化
    2. 每组参数通过 Walk-Forward Validation 在多个滚动时段上评估
    3. 优化完成后收集各策略最优信号序列（因子）
    4. 运行第二轮 Optuna 优化，寻找因子的最优组合权重
    5. 返回每个策略的最优参数 + 因子权重 + 组合结果
"""
from __future__ import annotations

import logging

import numpy as np
import optuna
import pandas as pd
from scipy.special import softmax

from app.config.config import config
from app.core.base_engine import BaseEngine, EngineResult
from app.core.base_strategy import BaseStrategy
from app.core.engine_registry import ENGINE_REGISTRY
from app.utils.helpers import set_global_seed
from app.utils.metrics import calmar_ratio, compute_all_metrics

logger = logging.getLogger("quant_engine.bayesian")

# 抑制 Optuna 的冗余日志
optuna.logging.set_verbosity(optuna.logging.WARNING)


class BayesianEngine(BaseEngine):
    """
    基于 Optuna 的贝叶斯超参数优化引擎（万能目标函数 + WFV + 因子权重元优化）
    """

    def __init__(self) -> None:
        super().__init__(
            name="Bayesian (Optuna)",
            description="Bayesian optimization with Walk-Forward Validation + factor weight meta-optimization",
        )

    def run(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        log_callback=None,
        **kwargs,
    ) -> EngineResult:
        """单策略入口（routes.py 对每个策略独立调用）"""
        def emit(msg: str) -> None:
            if log_callback:
                log_callback("info", msg)

        set_global_seed(config.default_seed)

        timeframe = kwargs.get("timeframe", config.default_timeframe)
        n_trials = kwargs.get("optuna_trials", config.bayesian_n_trials)
        n_splits = (
            config.bayesian_n_splits_quick if config.quick_mode
            else kwargs.get("wfv_folds", config.bayesian_n_splits)
        )

        # -----------------------------------------------------------------------
        # 【WFV min_train_size 动态缩放】
        # 不同时间框架下，同样的"252"代表的数据量差异巨大：
        #   1d: 252 bars ≈ 1年  ✅
        #   1h: 252 bars ≈ 10.5天  ❌（训练集太小，必过拟合）
        # 解决方案：按时间框架对 min_train_size 进行等比缩放。
        # -----------------------------------------------------------------------
        from app.utils.metrics import BARS_PER_YEAR
        bpy = BARS_PER_YEAR.get(timeframe, 365)
        min_train = max(
            50,
            int(config.bayesian_min_train_size * bpy / 365)
        )

        oos_split = kwargs.get("oos_split", 20.0) / 100.0
        split_idx = int(len(df) * (1 - oos_split))
        df_is = df.iloc[:split_idx]

        # ----------------------------------------------------------------
        # 【Walk-Forward Validation 分割点计算】
        #
        # 防过拟合核心架构：
        #   在量化交易中，随机划分数据（K-Fold交叉验证）等于"用未来预测历史"，
        #   这是绝对禁止的。WFV 严格保证时序：
        #
        #   [======Train_1=====][=Val_1=]
        #   [=========Train_2=========][=Val_2=]
        #   [===============Train_3=============][=Val_3=]
        #
        #   每折训练集都严格早于验证集，模拟真实的"先优化，后实盘"流程。
        #   多个不同历史区间（含牛市/熊市/震荡）的评估，
        #   使优胜参数必须在不同市场状态下均表现稳健。
        # ----------------------------------------------------------------
        total_is = len(df_is)
        fold_size = max(30, (total_is - min_train) // (n_splits + 1))

        splits = []
        for i in range(n_splits):
            train_end = min_train + fold_size * (i + 1)
            val_start = train_end
            val_end = min(val_start + fold_size, total_is)
            if val_end <= val_start:
                break
            splits.append((val_start, val_end))

        if not splits:
            splits = [(int(total_is * 0.7), total_is)]

        def objective(trial: optuna.Trial) -> tuple[float, float]:
            """
            多目标优化函数：同时最大化 Calmar Ratio 和 Sharpe Ratio。
            """
            params = strategy.get_param_space(trial)
            fold_calmars = []
            fold_sharpes = []

            for fold_idx, (val_start, val_end) in enumerate(splits):
                val_df = df_is.iloc[val_start:val_end]
                try:
                    val_returns = strategy.generate_signals(val_df, params)
                    cr = calmar_ratio(val_returns, timeframe=timeframe)
                    
                    # Compute sharpe ratio simply here (or import sharpe_ratio if available, using basic approximation)
                    mean_ret = val_returns.mean()
                    std_ret = val_returns.std()
                    from app.utils.metrics import BARS_PER_YEAR
                    bpy = BARS_PER_YEAR.get(timeframe, 365)
                    sr = (mean_ret / std_ret * np.sqrt(bpy)) if std_ret > 1e-8 else -10.0
                    
                    if not np.isfinite(cr):
                        cr = -10.0
                    if not np.isfinite(sr):
                        sr = -10.0
                except Exception as e:
                    logger.exception(f"Strategy {strategy.name} fold {fold_idx} evaluation failed")
                    cr = -10.0
                    sr = -10.0

                fold_calmars.append(cr)
                fold_sharpes.append(sr)

                # 对于多目标优化，不支持 MedianPruner 的简单 report，故移除中途剪枝

            return float(np.mean(fold_calmars)), float(np.mean(fold_sharpes))

        emit(f"[{self.name}] 策略: {strategy.name} | {n_trials} trials × {len(splits)} WFV folds (MOTPE Multi-Objective)")

        sampler = optuna.samplers.MOTPESampler(seed=config.default_seed)
        study = optuna.create_study(directions=["maximize", "maximize"], sampler=sampler)
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        # 从帕累托前沿 (Pareto Front) 选出最佳 trial
        best_trials = study.best_trials
        if not best_trials:
            best_trial = study.trials[0]
        else:
            # 启发式选择：归一化目标后求到理想点（最大Calmar, 最大Sharpe）距离最小的，或者简单加权
            calmars = np.array([t.values[0] for t in best_trials])
            sharpes = np.array([t.values[1] for t in best_trials])
            
            # 避免除以 0
            cal_range = calmars.max() - calmars.min() if calmars.max() > calmars.min() else 1.0
            shr_range = sharpes.max() - sharpes.min() if sharpes.max() > sharpes.min() else 1.0
            
            norm_cal = (calmars - calmars.min()) / cal_range
            norm_shr = (sharpes - sharpes.min()) / shr_range

            # 从 kwargs 获取用户定义的权重，默认为等权（50/50）
            calmar_weight = kwargs.get("calmar_weight", 0.5)
            sharpe_weight = kwargs.get("sharpe_weight", 0.5)

            # 归一化权重以确保总和为 1
            weight_sum = calmar_weight + sharpe_weight
            calmar_weight = calmar_weight / weight_sum if weight_sum > 0 else 0.5
            sharpe_weight = sharpe_weight / weight_sum if weight_sum > 0 else 0.5

            # 综合得分（加权组合）
            combined_scores = (norm_cal * calmar_weight) + (norm_shr * sharpe_weight)
            best_idx = np.argmax(combined_scores)

            emit(f"[{self.name}] 多目标权重: Calmar={calmar_weight:.1%}, Sharpe={sharpe_weight:.1%}")
            best_trial = best_trials[best_idx]

        best_params = best_trial.params
        emit(f"[{self.name}] 帕累托最优选择 -> Calmar: {best_trial.values[0]:.4f}, Sharpe: {best_trial.values[1]:.4f} | 参数: {best_params}")

        # OOS 全量评估（仅在训练时从未接触过的 OOS 区间）
        df_oos = df.iloc[split_idx:]
        final_returns = strategy.generate_signals(df_oos, best_params)
        benchmark_returns = df_oos["close"].pct_change()
        metrics = compute_all_metrics(final_returns, timeframe=timeframe, benchmark_returns=benchmark_returns)

        # ----------------------------------------------------------------
        # 提取 Optuna 历史数据（供前端散点收敛图使用，赛博朋克配色）
        # ----------------------------------------------------------------
        completed = [t for t in study.trials if t.value is not None]
        history_data = {
            "data": [
                {
                    "x": [t.number for t in completed],
                    "y": [t.value for t in completed],
                    "type": "scatter",
                    "mode": "markers",
                    "name": "Trial Score",
                    "marker": {"color": "#00FF41", "size": 5, "opacity": 0.7},
                },
                {
                    "x": [t.number for t in completed],
                    "y": _running_best([t.value for t in completed]),
                    "type": "scatter",
                    "mode": "lines",
                    "name": "Best So Far",
                    "line": {"color": "#C724FF", "width": 2},
                },
            ],
            "layout": {
                "title": f"[{strategy.name}] Optuna Convergence",
                "paper_bgcolor": "#050a05",
                "plot_bgcolor": "#050a05",
                "font": {"color": "#00FF41"},
                "xaxis": {"title": "Trial", "gridcolor": "#008F11"},
                "yaxis": {"title": "Calmar Ratio", "gridcolor": "#008F11"},
            },
        }

        # 参数重要性（赛博朋克配色）
        importance_data = None
        try:
            if len(completed) >= 10:
                importance = optuna.importance.get_param_importances(study)
                importance_data = {
                    "data": [{
                        "x": list(importance.values()),
                        "y": list(importance.keys()),
                        "type": "bar",
                        "orientation": "h",
                        "marker": {
                            "color": "#00FFFF",
                            "line": {"color": "#008F11", "width": 1},
                        },
                        "name": "Importance",
                    }],
                    "layout": {
                        "title": f"[{strategy.name}] Parameter Importance",
                        "paper_bgcolor": "#050a05",
                        "plot_bgcolor": "#050a05",
                        "font": {"color": "#00FF41"},
                        "xaxis": {"title": "Importance", "gridcolor": "#008F11"},
                        "yaxis": {"gridcolor": "#008F11"},
                    },
                }
        except Exception as e:
            logger.warning(f"参数重要性计算失败: {e}")

        extra_plots = {"history": history_data}
        if importance_data:
            extra_plots["importance"] = importance_data

        return EngineResult(
            best_params=best_params,
            sharpe=metrics["sharpe"],
            calmar=metrics["calmar"],
            max_drawdown=metrics["max_drawdown"],
            annual_return=metrics["annual_return"],
            equity_curve=metrics["equity_curve"],
            extra_plots=extra_plots,
        )


def run_factor_weight_optimization(
    strategy_signals: dict[str, pd.Series],
    timeframe: str = "1d",
    n_trials: int = 50,
) -> dict[str, float]:
    """
    因子权重元优化（多策略贝叶斯因子组合）

    将每个策略的最优信号序列视为"因子"，
    使用 Optuna TPE 搜索最优线性组合权重。

    等效于 Lasso/Ridge 对因子的筛选：
    权重趋向 0 的策略会被自然淘汰，不需要硬性剪枝。
    """
    strategy_ids = list(strategy_signals.keys())
    signals_list = [strategy_signals[sid] for sid in strategy_ids]

    # 对齐所有信号的时间索引
    combined_df = pd.concat(signals_list, axis=1)
    combined_df.columns = strategy_ids
    combined_df = combined_df.dropna()

    def factor_objective(trial: optuna.Trial) -> float:
        raw_weights = np.array([
            trial.suggest_float(sid, 0.0, 1.0) for sid in strategy_ids
        ])
        weights = softmax(raw_weights)
        combined = sum(
            w * combined_df[sid] for w, sid in zip(weights, strategy_ids)
        )
        cr = calmar_ratio(combined, timeframe=timeframe)
        return cr if np.isfinite(cr) else -10.0

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    factor_study = optuna.create_study(direction="maximize")
    factor_study.optimize(factor_objective, n_trials=n_trials, show_progress_bar=False)

    raw_best = np.array([factor_study.best_params[sid] for sid in strategy_ids])
    best_weights = softmax(raw_best)
    return {sid: float(w) for sid, w in zip(strategy_ids, best_weights)}


def _running_best(values: list[float]) -> list[float]:
    """计算历史最优序列（用于收敛曲线的品红折线）"""
    result = []
    best = float("-inf")
    for v in values:
        if v > best:
            best = v
        result.append(best)
    return result


ENGINE_REGISTRY.register("bayesian", BayesianEngine)
