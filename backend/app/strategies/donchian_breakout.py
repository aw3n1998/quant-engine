# backend/app/strategies/donchian_breakout.py
"""
Donchian Channel Breakout 策略（唐奇安通道突破）

核心思想:
    海龟交易法的核心：价格突破 N 日最高价做多，突破 N 日最低价做空。
    加密市场趋势性强（BTC 年均波动率 80%+），突破后动量延续概率高。
    用较短的 exit_period 实现快速止损，保留胜率较高的趋势段。

量化逻辑:
    1. 价格突破 entry_period 日最高价 → 做多（+1）
    2. 价格跌破 entry_period 日最低价 → 做空（-1）
    3. 多头平仓：价格跌破 exit_period 日最低价
    4. 空头平仓：价格突破 exit_period 日最高价
    5. 可选 ATR 止损过滤：避免在极低波动期假突破入场
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class DonchianBreakoutStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Donchian Channel Breakout",
            description="Turtle-style N-day high/low breakout with adaptive exit channel",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        entry_period = trial.suggest_int("entry_period", 10, 60)
        return {
            "entry_period": entry_period,
            "exit_period": trial.suggest_int("exit_period", 5, max(6, entry_period - 1)),
            "atr_period": trial.suggest_int("atr_period", 10, 30),
            "atr_min_mult": trial.suggest_float("atr_min_mult", 0.2, 1.5),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        ep = params["entry_period"]
        xp = params["exit_period"]
        atr_period = params["atr_period"]
        atr_min = params["atr_min_mult"]

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # 唐奇安通道
        entry_high = close.rolling(ep).max().shift(1)
        entry_low  = close.rolling(ep).min().shift(1)
        exit_high  = close.rolling(xp).max().shift(1)
        exit_low   = close.rolling(xp).min().shift(1)

        # ATR 过滤：仅在波动率足够时入场（防低波动期假突破）
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(atr_period).mean()
        atr_threshold = close * 0.005 * atr_min  # 至少是价格的 0.5% * mult

        position = pd.Series(0.0, index=df.index)
        pos = 0.0
        for i in range(ep, len(df)):
            atr_ok = atr.iloc[i] >= atr_threshold.iloc[i]
            c = close.iloc[i]

            if pos == 0.0:
                if atr_ok and c > entry_high.iloc[i]:
                    pos = 1.0
                elif atr_ok and c < entry_low.iloc[i]:
                    pos = -1.0
            elif pos == 1.0:
                if c < exit_low.iloc[i]:
                    pos = 0.0
            elif pos == -1.0:
                if c > exit_high.iloc[i]:
                    pos = 0.0

            position.iloc[i] = pos

        daily_ret = close.pct_change()
        return (position.shift(1) * daily_ret).fillna(0.0)


STRATEGY_REGISTRY.register("donchian_breakout", DonchianBreakoutStrategy())
