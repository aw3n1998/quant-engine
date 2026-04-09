# backend/app/strategies/regime_meta.py
"""
Regime Meta Strategy（市场状态自适应策略）

核心思想:
    传统策略在所有市场状态下使用同一套逻辑，导致在不适合的状态下亏损。
    本策略首先识别4种市场状态，再针对每种状态切换不同的信号逻辑：
    - 牛市（强趋势 + 低波动）→ EMA 趋势跟随
    - 熊市（强趋势 + 高波动）→ 均值回归（反向操作）
    - 盘整（弱趋势 + 低波动）→ RSI 超买超卖反转
    - 恐慌（弱趋势 + 极高波动）→ 停止交易（0仓位）
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


class RegimeMetaStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Regime Meta",
            description="Detects 4 market regimes (bull/bear/range/panic) and applies optimal logic per regime",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "atr_period":          trial.suggest_int("atr_period",          10, 30),
            "vol_threshold_low":   trial.suggest_float("vol_threshold_low",  0.008, 0.025),
            "vol_threshold_high":  trial.suggest_float("vol_threshold_high", 0.025, 0.07),
            "ema_fast":            trial.suggest_int("ema_fast",             8, 25),
            "ema_slow":            trial.suggest_int("ema_slow",             30, 100),
            "trend_threshold":     trial.suggest_float("trend_threshold",    0.003, 0.02),
            "rsi_period":          trial.suggest_int("rsi_period",           7, 21),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        atr_p   = params["atr_period"]
        vol_lo  = params["vol_threshold_low"]
        vol_hi  = params["vol_threshold_high"]
        ef      = params["ema_fast"]
        es      = params["ema_slow"]
        t_thr   = params["trend_threshold"]
        rsi_p   = params["rsi_period"]

        close = df["close"]

        # 波动率：ATR / close（相对波动率）
        atr       = _atr(df, atr_p)
        vol_ratio = atr / close

        # 趋势强度：EMA 偏离度
        ema_fast  = close.ewm(span=ef, adjust=False).mean()
        ema_slow  = close.ewm(span=es, adjust=False).mean()
        trend_str = ((ema_fast - ema_slow) / close).abs()
        trend_dir = (ema_fast > ema_slow).astype(float) * 2 - 1  # +1上升 -1下降

        rsi = _rsi(close, rsi_p)

        position  = pd.Series(0.0, index=df.index)
        daily_ret = close.pct_change()

        warmup = max(atr_p, es, rsi_p) + 5

        for i in range(warmup, len(df)):
            vol = vol_ratio.iloc[i]
            trd = trend_str.iloc[i]
            tdr = trend_dir.iloc[i]
            r   = rsi.iloc[i]

            if vol > vol_hi:
                # 恐慌：不交易
                pos = 0.0
            elif trd > t_thr and vol <= vol_lo:
                # 牛市/强趋势低波动：顺势跟随
                pos = tdr
            elif trd > t_thr and vol > vol_lo:
                # 熊市/强趋势高波动：反向均值回归
                pos = -tdr
            else:
                # 盘整：RSI 超买超卖
                if r < 35:
                    pos = 1.0
                elif r > 65:
                    pos = -1.0
                else:
                    pos = position.iloc[i - 1]  # 持仓不变

            position.iloc[i] = pos

        return (position.shift(1) * daily_ret).fillna(0.0)


STRATEGY_REGISTRY.register("regime_meta", RegimeMetaStrategy())
