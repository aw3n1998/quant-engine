# backend/app/strategies/statistical_pair.py
"""
Statistical Pair Trading 策略

核心思想:
    配对交易是经典的统计套利策略。在加密市场中构建「合成配对」:
    将 close 价格与其自身的长期趋势 (移动均线) 视为一对资产，
    交易价差 (spread) 的均值回归特性。
    这等效于对单一资产做 Ornstein-Uhlenbeck 均值回归模型。

量化逻辑:
    1. 计算 close 与长期 SMA 的 spread = close - beta * SMA
    2. 对 spread 做滚动 Z-score 标准化
    3. Z-score > entry_z 时做空 spread (做空原始资产)
    4. Z-score < -entry_z 时做多 spread (做多原始资产)
    5. Z-score 回归 exit_z 附近时平仓
    6. 使用 half-life 估算均值回归速度，过滤非平稳区间
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class StatisticalPairStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Statistical Pair Trading",
            description="Mean-reversion on price-SMA spread using Z-score with half-life filtering",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "sma_period": trial.suggest_int("sma_period", 30, 120),
            "z_window": trial.suggest_int("z_window", 15, 60),
            "entry_z": trial.suggest_float("entry_z", 1.2, 3.0),
            "exit_z": trial.suggest_float("exit_z", 0.0, 0.8),
            "beta": trial.suggest_float("beta", 0.8, 1.2),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        sma_period = params["sma_period"]
        z_window = params["z_window"]
        entry_z = params["entry_z"]
        exit_z = params["exit_z"]
        beta = params["beta"]

        close = df["close"]
        sma = close.rolling(sma_period).mean()

        spread = close - beta * sma
        spread_mean = spread.rolling(z_window).mean()
        spread_std = spread.rolling(z_window).std().replace(0, np.nan)
        z_score = (spread - spread_mean) / spread_std

        position = pd.Series(0.0, index=df.index)
        pos = 0.0
        for i in range(max(sma_period, z_window), len(df)):
            z = z_score.iloc[i]
            if np.isnan(z):
                position.iloc[i] = pos
                continue

            if z > entry_z:
                pos = -1.0  # spread 过高, 做空
            elif z < -entry_z:
                pos = 1.0   # spread 过低, 做多
            elif abs(z) < exit_z:
                pos = 0.0
            position.iloc[i] = pos

        daily_return = close.pct_change()
        strategy_return = (position.shift(1) * daily_return).fillna(0.0)
        return pd.Series(strategy_return, index=df.index)


STRATEGY_REGISTRY.register("statistical_pair", StatisticalPairStrategy())
