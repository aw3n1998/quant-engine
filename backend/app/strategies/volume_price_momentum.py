# backend/app/strategies/volume_price_momentum.py
"""
Volume-Price Momentum（量价共振动量）策略

核心思想:
    真实的趋势突破必须有成交量放大确认，否则是虚假突破（主力洗盘）。
    价格创 N 日新高 且 成交量超过 M 日均量的 K 倍 → 大资金推动的真实突破。
    做空逻辑相反：价格创 N 日新低 且 成交量放大 → 恐慌性抛售跟随做空。
    持仓管理：ATR 追踪止损，避免回撤过大。

量化逻辑:
    1. price_breakout_up   = close == rolling_max(price_period)
    2. price_breakout_down = close == rolling_min(price_period)
    3. vol_surge           = volume > rolling_mean(vol_period) * vol_mult
    4. 做多：price_breakout_up  & vol_surge
    5. 做空：price_breakout_down & vol_surge
    6. 退出：ATR 追踪止损 或 持仓超过 max_hold 根 K 线
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class VolumePriceMomentumStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Volume-Price Momentum",
            description="N-day price breakout confirmed by volume surge, with ATR trailing stop",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "price_period": trial.suggest_int("price_period",  10, 50),
            "vol_period":   trial.suggest_int("vol_period",    10, 30),
            "vol_mult":     trial.suggest_float("vol_mult",    1.5, 4.0),
            "atr_period":   trial.suggest_int("atr_period",    10, 20),
            "atr_stop_mult":trial.suggest_float("atr_stop_mult", 1.0, 3.0),
            "max_hold":     trial.suggest_int("max_hold",      5, 30),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        pp   = params["price_period"]
        vp   = params["vol_period"]
        vm   = params["vol_mult"]
        atrp = params["atr_period"]
        asm  = params["atr_stop_mult"]
        mh   = params["max_hold"]

        close  = df["close"]
        high   = df["high"]
        low    = df["low"]
        volume = df["volume"]

        # 价格新高/新低（与前一根比：避免用当根自身）
        roll_max = close.shift(1).rolling(pp).max()
        roll_min = close.shift(1).rolling(pp).min()
        breakout_up   = close >= roll_max
        breakout_down = close <= roll_min

        # 成交量放量
        vol_ma  = volume.rolling(vp).mean()
        vol_surge = volume > vol_ma * vm

        # ATR 追踪止损
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(atrp).mean()

        position  = pd.Series(0.0, index=df.index)
        pos       = 0.0
        entry_price = 0.0
        bars_held   = 0
        warmup = max(pp, vp, atrp) + 1

        for i in range(warmup, len(df)):
            c    = close.iloc[i]
            atr_v = atr.iloc[i]

            if pos == 0.0:
                if breakout_up.iloc[i] and vol_surge.iloc[i]:
                    pos = 1.0
                    entry_price = c
                    bars_held = 0
                elif breakout_down.iloc[i] and vol_surge.iloc[i]:
                    pos = -1.0
                    entry_price = c
                    bars_held = 0
            else:
                bars_held += 1
                hit_stop = (
                    (pos ==  1.0 and c < entry_price - asm * atr_v) or
                    (pos == -1.0 and c > entry_price + asm * atr_v)
                )
                if hit_stop or bars_held >= mh:
                    pos = 0.0
                    bars_held = 0

            position.iloc[i] = pos

        daily_ret = close.pct_change()
        return (position.shift(1) * daily_ret).fillna(0.0)


STRATEGY_REGISTRY.register("volume_price_momentum", VolumePriceMomentumStrategy())
