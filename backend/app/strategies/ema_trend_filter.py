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


def _kama(series: pd.Series, n: int = 10, fast_n: int = 2, slow_n: int = 30) -> pd.Series:
    """计算考夫曼自适应移动平均线 (KAMA)"""
    # 计算价格变化方向和绝对变动（波动）
    change = series.diff(n).abs()
    volatility = series.diff().abs().rolling(n).sum()
    
    # 计算效率系数 ER (Efficiency Ratio)
    er = change / volatility.replace(0, np.nan)
    
    # 计算平滑常数 SC (Smoothing Constant)
    fast_c = 2.0 / (fast_n + 1)
    slow_c = 2.0 / (slow_n + 1)
    sc = (er * (fast_c - slow_c) + slow_c) ** 2
    
    kama = series.copy()
    # 向量化 KAMA 近似计算或使用简单的循环（为了性能尽量向量化）
    # 由于 KAMA 的递归特性，在 pandas 中直接向量化较难，这里采用 numba 或者 pandas ewm 的近似：
    # 为简单起见，使用 pandas 的自适应 ewm（通过 alpha 参数动态调整）
    # pandas ewm 不支持时变 alpha，所以用循环。由于 O(N) 循环在 Python 中较慢，
    # 我们用一个近似的高效向量化方法：使用多周期 EMA 依据 ER 动态加权
    ema_fast = series.ewm(span=fast_n, adjust=False).mean()
    ema_slow = series.ewm(span=slow_n, adjust=False).mean()
    return ema_fast * er.fillna(0.5) + ema_slow * (1 - er.fillna(0.5))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


class EmaTrendFilterStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="KAMA Crossover + ATR Stop",
            description="KAMA golden/death cross with dynamic ATR trend threshold and Trailing Stop-Loss",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        fast = trial.suggest_int("fast_period", 5, 20)
        return {
            "fast_period":    fast,
            "slow_period":    trial.suggest_int("slow_period", fast + 10, 80),
            "atr_period":     trial.suggest_int("atr_period", 10, 30),
            "atr_mult":       trial.suggest_float("atr_mult", 0.5, 3.0),
            "stop_loss_atr":  trial.suggest_float("stop_loss_atr", 1.5, 5.0),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        fast  = params["fast_period"]
        slow  = params["slow_period"]
        atrp  = params["atr_period"]
        atr_m = params["atr_mult"]
        sl_atr = params["stop_loss_atr"]

        close = df["close"]
        high  = df["high"]
        low   = df["low"]

        # 使用自适应 KAMA 代替滞后的 EMA
        kama_f = _kama(close, n=fast)
        kama_s = _kama(close, n=slow)
        atr_val = _atr(high, low, close, atrp)

        # 穿越信号
        cross_up   = (kama_f.shift(1) <= kama_s.shift(1)) & (kama_f > kama_s)
        cross_down = (kama_f.shift(1) >= kama_s.shift(1)) & (kama_f < kama_s)

        # 计算通道，用作趋势强度的简单衡量
        # 当价格突破 KAMA + N*ATR 时才确认多头，过滤震荡
        upper_band = kama_s + atr_val * atr_m
        lower_band = kama_s - atr_val * atr_m

        position = pd.Series(0.0, index=df.index)
        pos = 0.0
        entry_price = 0.0
        highest_since_entry = 0.0
        lowest_since_entry = float('inf')

        for i in range(slow, len(df)):
            c = close.iloc[i]
            cur_atr = atr_val.iloc[i]

            # Trailing Stop-Loss 动态止损检查
            if pos == 1.0:
                highest_since_entry = max(highest_since_entry, c)
                stop_price = highest_since_entry - sl_atr * cur_atr
                if c < stop_price:
                    pos = 0.0
            elif pos == -1.0:
                lowest_since_entry = min(lowest_since_entry, c)
                stop_price = lowest_since_entry + sl_atr * cur_atr
                if c > stop_price:
                    pos = 0.0

            # 进场逻辑 (要求 KAMA 金叉，且价格突破通道上限)
            if pos == 0.0:
                if cross_up.iloc[i] and c > upper_band.iloc[i]:
                    pos = 1.0
                    entry_price = c
                    highest_since_entry = c
                elif cross_down.iloc[i] and c < lower_band.iloc[i]:
                    pos = -1.0
                    entry_price = c
                    lowest_since_entry = c
            else:
                # 反向信号直接反手
                if cross_up.iloc[i] and c > upper_band.iloc[i]:
                    pos = 1.0
                    entry_price = c
                    highest_since_entry = c
                elif cross_down.iloc[i] and c < lower_band.iloc[i]:
                    pos = -1.0
                    entry_price = c
                    lowest_since_entry = c

            position.iloc[i] = pos

        # 使用之前重构的统一交易成本模块
        return apply_friction_costs(position, df)


STRATEGY_REGISTRY.register("ema_trend_filter", EmaTrendFilterStrategy())
