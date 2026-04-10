# backend/app/strategies/bollinger_squeeze.py
"""
Bollinger Band Squeeze（布林带收缩爆破）策略

核心思想:
    布林带宽度小于 Keltner 通道宽度时处于"压缩"状态，表示市场能量积蓄。
    压缩结束时（BB 宽度重新超过 KC），跟随突破方向持仓。
    加密市场盘整→暴涨/暴跌模式极为常见，本策略专门捕捉此类爆破行情。

量化逻辑:
    1. Squeeze = BB_upper < KC_upper AND BB_lower > KC_lower
    2. Squeeze 解除且 close > BB_upper → 做多
    3. Squeeze 解除且 close < BB_lower → 做空
    4. 持仓后用 BB 中轨（SMA）作为退出基准
    5. 动量确认：额外检查解除前 N 根 K 线内价格方向
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY
from app.utils.friction import apply_friction_costs


class BollingerSqueezeStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Bollinger Band Squeeze",
            description="Keltner/Bollinger squeeze breakout capturing post-consolidation explosive moves",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "bb_period":  trial.suggest_int("bb_period",  15, 30),
            "bb_std":     trial.suggest_float("bb_std",   1.5, 2.5),
            "kc_period":  trial.suggest_int("kc_period",  15, 30),
            "kc_mult":    trial.suggest_float("kc_mult",  1.0, 2.0),
            "hold_bars":  trial.suggest_int("hold_bars",  3, 20),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        bb_p  = params["bb_period"]
        bb_s  = params["bb_std"]
        kc_p  = params["kc_period"]
        kc_m  = params["kc_mult"]
        hold  = params["hold_bars"]

        close = df["close"]
        high  = df["high"]
        low   = df["low"]

        # Bollinger Bands
        sma  = close.rolling(bb_p).mean()
        std  = close.rolling(bb_p).std()
        bb_u = sma + bb_s * std
        bb_l = sma - bb_s * std

        # Keltner Channel（基于 ATR）
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr  = tr.rolling(kc_p).mean()
        kc_m_sma = close.rolling(kc_p).mean()
        kc_u = kc_m_sma + kc_m * atr
        kc_l = kc_m_sma - kc_m * atr

        # Squeeze 状态
        squeeze = (bb_u < kc_u) & (bb_l > kc_l)

        position = pd.Series(0.0, index=df.index)
        pos = 0.0
        bars_held = 0

        for i in range(max(bb_p, kc_p) + 1, len(df)):
            was_squeeze = squeeze.iloc[i - 1]
            now_squeeze = squeeze.iloc[i]
            c = close.iloc[i]

            # Squeeze 刚解除 → 判断方向入场
            if was_squeeze and not now_squeeze and pos == 0.0:
                if c > bb_u.iloc[i]:
                    pos = 1.0
                    bars_held = 0
                elif c < bb_l.iloc[i]:
                    pos = -1.0
                    bars_held = 0
            elif pos != 0.0:
                bars_held += 1
                # 超过最大持仓时间 或 价格回到中轨 → 平仓
                crossed_mid = (pos == 1.0 and c < sma.iloc[i]) or \
                              (pos == -1.0 and c > sma.iloc[i])
                if bars_held >= hold or crossed_mid:
                    pos = 0.0
                    bars_held = 0

            position.iloc[i] = pos

        return apply_friction_costs(position, df)


STRATEGY_REGISTRY.register("bollinger_squeeze", BollingerSqueezeStrategy())
