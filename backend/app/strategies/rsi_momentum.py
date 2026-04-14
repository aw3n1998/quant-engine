# backend/app/strategies/rsi_momentum.py
"""
RSI Momentum（RSI 动量区间跟随）策略

核心思想:
    区别于传统 RSI 超买卖反转（RSI>70卖/RSI<30买），
    本策略使用"动量确认模式"：
    - RSI 从超卖区恢复并突破中轴50 → 动量转正，顺势做多
    - RSI 从超买区回落并跌破中轴50 → 动量转负，顺势做空
    结合回望确认：要求 N 根K线前RSI处于极值区才认为是有效的动量反转。
    在趋势延续和趋势反转两种场景下均有效。

量化逻辑:
    1. 计算 RSI(period)
    2. 做多：RSI 突破50 且 M根前 RSI < oversold(30)
    3. 做空：RSI 跌破50 且 M根前 RSI > overbought(70)
    4. 止损：RSI 反向再次越过50
    5. 可选：价格动量确认（close > EMA(trend_ma) 才做多）
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY
from app.utils.friction import apply_friction_costs
from app.utils.numba_indicators import fast_ema, get_fast_rsi


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


class RsiMomentumStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="RSI Momentum",
            description="RSI midline crossover with extremal lookback confirmation for momentum trades",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "rsi_period":   trial.suggest_int("rsi_period",   8, 21),
            "lookback":     trial.suggest_int("lookback",     3, 15),
            "oversold":     trial.suggest_float("oversold",   25.0, 40.0),
            "overbought":   trial.suggest_float("overbought", 60.0, 75.0),
            "trend_ma":     trial.suggest_int("trend_ma",     50, 200),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        rsi_p  = params["rsi_period"]
        lb     = params["lookback"]
        os     = params["oversold"]
        ob     = params["overbought"]
        tma    = params["trend_ma"]

        close = df["close"]
        rsi   = get_fast_rsi(close, rsi_p)
        trend = pd.Series(fast_ema(close.values, tma), index=close.index)

        # RSI 穿越中轴
        cross_up   = (rsi.shift(1) <= 50) & (rsi > 50)
        cross_down = (rsi.shift(1) >= 50) & (rsi < 50)

        # 过去 lookback 根内曾处于极值区
        was_oversold  = rsi.shift(1).rolling(lb).min() < os
        was_overbought = rsi.shift(1).rolling(lb).max() > ob

        # 趋势过滤：多头需价格在长期均线上方
        trend_up   = close > trend
        trend_down = close < trend

        position = pd.Series(0.0, index=df.index)
        pos = 0.0
        warmup = max(rsi_p, tma, lb) + 5

        for i in range(warmup, len(df)):
            if cross_up.iloc[i] and was_oversold.iloc[i] and trend_up.iloc[i]:
                pos = 1.0
            elif cross_down.iloc[i] and was_overbought.iloc[i] and trend_down.iloc[i]:
                pos = -1.0
            elif pos == 1.0 and cross_down.iloc[i]:
                pos = 0.0
            elif pos == -1.0 and cross_up.iloc[i]:
                pos = 0.0

            position.iloc[i] = pos

        return apply_friction_costs(position, df)


STRATEGY_REGISTRY.register("rsi_momentum", RsiMomentumStrategy())
