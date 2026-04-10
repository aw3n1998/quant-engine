# backend/app/engines/risk_parity_engine.py
"""
Risk Parity Engine（风险平价引擎）

核心方法: 等风险贡献（Equal Risk Contribution）

工作流程:
    1. 对每个策略在 IS 数据上生成信号（使用默认中值参数）
    2. 计算每个策略信号的滚动波动率（标准差）
    3. 权重 = 1 / 波动率（逆波动率加权），归一化后得到等风险权重
    4. OOS 阶段逐根K线按当前波动率估计动态调整权重
    5. 结果：各策略对组合风险贡献大致相等

等风险 vs 等权:
    - 等权：每个策略相同金额，高波动策略贡献更多风险
    - 等风险：高波动策略自动降权，低波动策略升权，风险贡献均等

优势:
    - 不依赖收益预测，纯风险管理视角
    - 在不确定市场下比等权更稳健
    - 自动适应策略波动率变化

参数:
    - vol_window: 计算滚动波动率的窗口（默认 20 根K线）
    - vol_floor:  波动率下限，防止除零（默认 1e-4）
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from app.core.base_engine import BaseEngine, EngineResult
from app.core.base_strategy import BaseStrategy
from app.core.engine_registry import ENGINE_REGISTRY
from app.utils.metrics import compute_all_metrics

logger = logging.getLogger("quant_engine.risk_parity")


class _FakeTrial:
    def suggest_int(self, name: str, low: int, high: int, **kw) -> int:
        return (low + high) // 2

    def suggest_float(self, name: str, low: float, high: float, **kw) -> float:
        return (low + high) / 2


class RiskParityEngine(BaseEngine):
    def __init__(self) -> None:
        super().__init__(
            name="Risk Parity (Equal Risk Contribution)",
            description="Weights strategies by inverse signal volatility — equal risk contribution from each strategy",
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

        strategies: list[BaseStrategy] = strategy if isinstance(strategy, list) else [strategy]
        timeframe: str    = kwargs.get("timeframe", "1d")
        oos_split: float  = kwargs.get("oos_split", 20.0)
        vol_window: int   = kwargs.get("vol_window", 20)
        vol_floor: float  = kwargs.get("vol_floor", 1e-4)

        n = len(strategies)
        emit(f"[RiskParity] 初始化 | {n} 个策略 | vol_window={vol_window}")

        # 划分 IS / OOS
        split_idx = int(len(df) * (1 - oos_split / 100))
        df_is  = df.iloc[:split_idx].reset_index(drop=True)
        df_oos = df.iloc[split_idx:].reset_index(drop=True)

        if len(df_is) < vol_window + 10:
            emit("[RiskParity] IS 数据不足", "warning")
            return EngineResult()

        fake_trial = _FakeTrial()
        strategy_names: list[str]    = []
        is_signals:  list[pd.Series] = []
        oos_signals: list[pd.Series] = []

        emit("[RiskParity] 生成策略信号...")
        for s in strategies:
            try:
                params   = s.get_param_space(fake_trial)
                is_sig   = s.generate_signals(df_is,  params)
                oos_sig  = s.generate_signals(df_oos, params)
            except Exception:
                is_sig   = pd.Series(0.0, index=df_is.index)
                oos_sig  = pd.Series(0.0, index=df_oos.index)
            is_signals.append(is_sig)
            oos_signals.append(oos_sig)
            strategy_names.append(s.name)

        # ─── IS 段：计算各策略滚动波动率 → 静态权重 ───
        is_vols: list[float] = []
        for sig in is_signals:
            # 使用 IS 段整体标准差作为稳定估计
            vol = float(sig.std())
            is_vols.append(max(vol, vol_floor))

        inv_vols = np.array([1.0 / v for v in is_vols])
        static_weights = inv_vols / inv_vols.sum()

        for s, w, v in zip(strategies, static_weights, is_vols):
            emit(f"[RiskParity]   {s.name}: IS vol={v:.5f} → 权重={w:.4f}")

        # ─── OOS 段：逐根K线动态更新权重（滚动波动率）───
        # 用 concat IS + OOS 尾部来计算滚动窗口
        all_signals_concat = [
            pd.concat([is_signals[i], oos_signals[i]], ignore_index=True)
            for i in range(n)
        ]
        is_len = len(df_is)

        oos_combined = pd.Series(0.0, index=df_oos.index)
        weight_history: list[list[float]] = []

        for t in range(len(df_oos)):
            global_t = is_len + t
            # 计算各策略在滚动窗口内的波动率
            window_vols = []
            for i in range(n):
                window_start = max(0, global_t - vol_window)
                window_slice = all_signals_concat[i].iloc[window_start:global_t]
                vol = float(window_slice.std()) if len(window_slice) > 1 else is_vols[i]
                window_vols.append(max(vol, vol_floor))

            inv_v = np.array([1.0 / v for v in window_vols])
            dyn_weights = inv_v / inv_v.sum()
            weight_history.append(dyn_weights.tolist())

            # 加权合并当根K线收益
            ret_t = sum(dyn_weights[i] * oos_signals[i].iloc[t] for i in range(n))
            oos_combined.iloc[t] = ret_t

        metrics = compute_all_metrics(oos_combined, timeframe=timeframe)

        best_params_out = {
            f"static_w_{s.name}": round(float(static_weights[i]), 4)
            for i, s in enumerate(strategies)
        }
        best_params_out["vol_window"] = vol_window

        emit(f"[RiskParity] OOS Sharpe={metrics['sharpe']:.3f} | Calmar={metrics['calmar']:.3f}")

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


ENGINE_REGISTRY.register("risk_parity", RiskParityEngine)
