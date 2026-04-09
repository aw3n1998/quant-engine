# backend/app/strategies/mad_trend.py
"""
MAD Trend 策略

核心思想:
    使用平均绝对偏差 (Mean Absolute Deviation, MAD) 度量价格离散程度，
    构建自适应趋势通道。当价格突破通道上轨时做多，跌破下轨时做空。
    MAD 比标准差对异常值更鲁棒，适合加密货币的厚尾分布。

量化逻辑:
    1. 计算收盘价的滚动均值 (SMA)
    2. 计算收盘价相对 SMA 的滚动 MAD
    3. 上轨 = SMA + multiplier * MAD，下轨 = SMA - multiplier * MAD
    4. 价格突破上轨做多，跌破下轨做空，区间内维持当前仓位
    5. 结合成交量确认: 突破时成交量需高于滚动均量
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class MADTrendStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="MAD Trend",
            description="Adaptive trend channel using Mean Absolute Deviation with volume confirmation",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "window": trial.suggest_int("window", 10, 60),
            "multiplier": trial.suggest_float("multiplier", 1.0, 4.0),
            "vol_window": trial.suggest_int("vol_window", 5, 30),
            "vol_threshold": trial.suggest_float("vol_threshold", 0.8, 1.5),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        window = params["window"]
        mult = params["multiplier"]
        vol_window = params["vol_window"]
        vol_thresh = params["vol_threshold"]

        close = df["close"]
        sma = close.rolling(window).mean()

        # MAD: 每个窗口内各值与均值的平均绝对偏差
        mad = close.rolling(window).apply(
            lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
        )

        upper = sma + mult * mad
        lower = sma - mult * mad

        vol_ma = df["volume"].rolling(vol_window).mean()
        vol_confirm = df["volume"] > vol_thresh * vol_ma

        long_signal = (close > upper) & vol_confirm
        short_signal = (close < lower) & vol_confirm
        raw_pos = pd.Series(np.nan, index=df.index)
        raw_pos[long_signal] = 1.0
        raw_pos[short_signal] = -1.0
        raw_pos.iloc[:window] = 0.0
        position = raw_pos.ffill().fillna(0.0)

        daily_return = close.pct_change()
        strategy_return = (position.shift(1) * daily_return).fillna(0.0)
        return pd.Series(strategy_return, index=df.index)


STRATEGY_REGISTRY.register("mad_trend", MADTrendStrategy())
