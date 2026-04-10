# backend/app/strategies/ema_trend_filter.py
"""
EMA Crossover + ADX Trend Filter（双EMA交叉 + ADX趋势强度过滤）策略

核心思想:
    EMA 短期上穿长期为金叉做多，下穿为死叉做空。
    单独用 EMA 穿越在震荡市会产生大量假信号。
    ADX（平均趋向指数）> 阈值时才确认趋势存在，过滤掉震荡期的假穿越。
    ADX 只关心趋势强度，不区分多空，配合 EMA 方向使用。

量化逻辑:
    1. 计算 EMA(fast) 和 EMA(slow)
    2. 计算 ADX(adx_period)
    3. 金叉 且 ADX > threshold → 做多（+1）
    4. 死叉 且 ADX > threshold → 做空（-1）
    5. ADX 降到 exit_adx 以下时减仓退出（趋势消退）
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY
from app.utils.friction import apply_friction_costs


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """计算 ADX（平均趋向指数）"""
    up   = high.diff()
    down = -low.diff()
    plus_dm  = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    atr      = tr.ewm(span=period, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return dx.ewm(span=period, adjust=False).mean()


class EmaTrendFilterStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="EMA Crossover + ADX Filter",
            description="EMA golden/death cross with ADX trend strength gate to eliminate whipsaws",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        fast = trial.suggest_int("fast_period", 5, 30)
        return {
            "fast_period":    fast,
            "slow_period":    trial.suggest_int("slow_period", fast + 5, 80),
            "adx_period":     trial.suggest_int("adx_period", 10, 28),
            "adx_threshold":  trial.suggest_float("adx_threshold", 18.0, 35.0),
            "exit_adx":       trial.suggest_float("exit_adx", 10.0, 22.0),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        fast  = params["fast_period"]
        slow  = params["slow_period"]
        adxp  = params["adx_period"]
        adx_t = params["adx_threshold"]
        exit_a = params["exit_adx"]

        close = df["close"]
        high  = df["high"]
        low   = df["low"]

        ema_f = _ema(close, fast)
        ema_s = _ema(close, slow)
        adx   = _adx(high, low, close, adxp)

        # 穿越信号
        cross_up   = (ema_f.shift(1) <= ema_s.shift(1)) & (ema_f > ema_s)
        cross_down = (ema_f.shift(1) >= ema_s.shift(1)) & (ema_f < ema_s)

        position = pd.Series(0.0, index=df.index)
        pos = 0.0
        for i in range(slow + adxp, len(df)):
            adx_val = adx.iloc[i]

            if cross_up.iloc[i] and adx_val > adx_t:
                pos = 1.0
            elif cross_down.iloc[i] and adx_val > adx_t:
                pos = -1.0
            elif pos != 0.0 and adx_val < exit_a:
                pos = 0.0

            position.iloc[i] = pos

        return apply_friction_costs(position, df)


STRATEGY_REGISTRY.register("ema_trend_filter", EmaTrendFilterStrategy())
