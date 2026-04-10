# backend/app/strategies/fibonacci_resonance.py
"""
Fibonacci Resonance 策略

核心思想:
    利用斐波那契回撤位 (38.2%, 50.0%, 61.8%) 作为关键支撑/阻力区域。
    当价格回撤至斐波那契关键水平附近并出现趋势反转信号时入场。
    使用最近 N 根 K 线的高低点确定斐波那契框架，并结合
    动量指标 (ROC) 确认反转方向。

量化逻辑:
    1. 滚动窗口内计算最高价和最低价
    2. 计算当前价格相对于高低范围的回撤比例
    3. 当回撤比例接近 0.382/0.500/0.618 且 ROC 为正时做多
    4. 当回撤比例接近 0.382/0.500/0.618 且 ROC 为负时做空
    5. 未触发信号时持平
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY
from app.utils.friction import apply_friction_costs


class FibonacciResonanceStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Fibonacci Resonance",
            description="Trade reversals at Fibonacci retracement levels with momentum confirmation",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "lookback": trial.suggest_int("lookback", 10, 60),
            "fib_tolerance": trial.suggest_float("fib_tolerance", 0.02, 0.10),
            "roc_period": trial.suggest_int("roc_period", 3, 20),
            "stop_loss": trial.suggest_float("stop_loss", 0.01, 0.05),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        lookback = params["lookback"]
        tol = params["fib_tolerance"]
        roc_period = params["roc_period"]
        stop_loss = params["stop_loss"]

        close = df["close"]
        high_roll = df["high"].rolling(lookback).max()
        low_roll = df["low"].rolling(lookback).min()

        span = high_roll - low_roll
        span = span.replace(0, np.nan)
        retracement = (close - low_roll) / span

        roc = close.pct_change(roc_period)

        fib_levels = [0.382, 0.500, 0.618]

        position = pd.Series(0.0, index=df.index)
        for lvl in fib_levels:
            near_fib = (retracement - lvl).abs() < tol
            position = position + np.where(near_fib & (roc > 0), 1.0, 0.0)
            position = position + np.where(near_fib & (roc < 0), -1.0, 0.0)

        position = position.clip(-1, 1)

        # 先扣除摩擦成本，再计算止损（净收益的累计回撤触发止损更真实）
        net_return = apply_friction_costs(position, df)

        # 简易止损: 净收益累计回撤超过阈值则清仓
        cumulative = (1 + net_return).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        net_return = np.where(drawdown < -stop_loss, 0.0, net_return)

        return pd.Series(net_return, index=df.index)


STRATEGY_REGISTRY.register("fibonacci_resonance", FibonacciResonanceStrategy())
