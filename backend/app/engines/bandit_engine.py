# backend/app/engines/bandit_engine.py
"""
Thompson Sampling Bandit Engine（在线学习多臂老虎机引擎）

核心方法: Beta 分布 Thompson 采样

工作流程:
    1. 为每个策略初始化 Beta(1, 1) 先验（均匀分布）
    2. 在样本内数据上逐根K线进行在线学习：
       a. 从每个策略的 Beta 分布采样得到"预期收益"
       b. Softmax 归一化为权重
       c. 计算加权组合收益
       d. 根据各策略实际表现更新 Beta 参数
    3. 用最终学到的权重在样本外数据上评估
    4. 记录完整的权重时序（weight_history）

优势：
    - 在线学习，无需离线优化
    - 自动平衡探索（exploration）和利用（exploitation）
    - 计算速度快，适合实时自适应

设计细节：
    - 本引擎使用 default params {} 获取策略信号，不进行超参优化
    - 权重学习仅基于 IS 数据，OOS 阶段使用固定最终权重评估
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.special import softmax

from app.core.base_engine import BaseEngine, EngineResult
from app.core.base_strategy import BaseStrategy
from app.core.engine_registry import ENGINE_REGISTRY
from app.utils.metrics import compute_all_metrics

logger = logging.getLogger("quant_engine.bandit")


class BanditEngine(BaseEngine):
    def __init__(self) -> None:
        super().__init__(
            name="Thompson Sampling Bandit",
            description="Online learning via Beta-distribution Thompson sampling — adapts weights bar-by-bar",
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

        # 支持多策略（routes.py 通过 strategies 列表传入）
        strategies: list[BaseStrategy] = kwargs.get("strategies", [strategy])
        timeframe: str = kwargs.get("timeframe", "1d")
        oos_split: float = kwargs.get("oos_split", 20.0)

        n = len(strategies)
        emit(f"[Bandit] 初始化 Thompson Sampling | {n} 个策略 | {len(df)} 根K线")

        # 划分 IS / OOS
        split_idx = int(len(df) * (1 - oos_split / 100))
        df_is  = df.iloc[:split_idx].reset_index(drop=True)
        df_oos = df.iloc[split_idx:].reset_index(drop=True)

        if len(df_is) < 50:
            emit("[Bandit] IS 数据不足，返回空结果", "warning")
            return EngineResult()

        # 生成各策略在 IS 上的信号（使用默认参数）
        default_params = {}
        is_signals: list[pd.Series] = []
        strategy_names: list[str]   = []
        for s in strategies:
            try:
                trial_params = s.get_param_space(_FakeTrial(s))
                sig = s.generate_signals(df_is, trial_params)
            except Exception:
                sig = pd.Series(0.0, index=df_is.index)
            is_signals.append(sig)
            strategy_names.append(s.name)

        # ─── Thompson Sampling 在线学习 ───
        alpha = np.ones(n)   # Beta 分布参数（成功次数 + 1）
        beta_ = np.ones(n)   # Beta 分布参数（失败次数 + 1）

        weight_history: list[list[float]] = []
        rng = np.random.default_rng(42)

        emit("[Bandit] 开始在线学习 IS 阶段...")
        for t in range(len(df_is)):
            # 1. 从每个 Beta 分布采样
            theta = rng.beta(alpha, beta_)

            # 2. Softmax 归一化为权重
            weights = softmax(theta * 3)  # 温度系数 3 增强对比
            weight_history.append(weights.tolist())

            # 3. 更新 Beta 参数（根据该K线各策略实际表现）
            for i, sig in enumerate(is_signals):
                ret_i = sig.iloc[t]
                if ret_i > 0:
                    alpha[i] += 1
                elif ret_i < 0:
                    beta_[i] += 1

        emit("[Bandit] IS 学习完成，计算最终权重...")

        # 最终权重：基于学到的期望收益
        final_weights = softmax(alpha / (alpha + beta_) * 3)
        emit(f"[Bandit] 最终权重: {dict(zip(strategy_names, [round(w, 3) for w in final_weights]))}")

        # ─── OOS 评估 ───
        oos_signals: list[pd.Series] = []
        for s in strategies:
            try:
                trial_params = s.get_param_space(_FakeTrial(s))
                sig = s.generate_signals(df_oos, trial_params)
            except Exception:
                sig = pd.Series(0.0, index=df_oos.index)
            oos_signals.append(sig)

        # 组合 OOS 收益
        oos_combined = pd.Series(0.0, index=df_oos.index)
        for i, sig in enumerate(oos_signals):
            oos_combined += final_weights[i] * sig

        metrics = compute_all_metrics(oos_combined, timeframe=timeframe)

        best_params = {s.name: float(round(w, 4)) for s, w in zip(strategies, final_weights)}

        emit(f"[Bandit] OOS Sharpe={metrics['sharpe']:.3f} | Calmar={metrics['calmar']:.3f}")

        return EngineResult(
            best_params=best_params,
            sharpe=metrics["sharpe"],
            calmar=metrics["calmar"],
            max_drawdown=metrics["max_drawdown"],
            annual_return=metrics["annual_return"],
            equity_curve=metrics["equity_curve"],
            weight_history=weight_history,
            strategy_names=strategy_names,
        )


class _FakeTrial:
    """模拟 Optuna Trial 以获取默认参数（取建议范围中值）"""
    def __init__(self, strategy: BaseStrategy):
        self._strategy = strategy

    def suggest_int(self, name: str, low: int, high: int, **kw) -> int:
        return (low + high) // 2

    def suggest_float(self, name: str, low: float, high: float, **kw) -> float:
        return (low + high) / 2


ENGINE_REGISTRY.register("bandit", BanditEngine)
