# backend/app/strategies/liquidation_hunting.py
"""
Liquidation Hunting 策略

核心思想:
    加密货币市场中大量高杠杆头寸的强制平仓 (liquidation) 会导致瀑布式价格变动。
    当价格接近大量止损/爆仓集中区域时，一旦触发连环清算，
    价格会剧烈单向波动后迅速反弹。本策略试图:
    1. 识别潜在的清算级联事件 (通过价格加速度和成交量激增)
    2. 在清算结束后的反弹中入场

量化逻辑:
    1. 计算价格加速度: 二阶价格变化 (returns 的 diff)
    2. 计算成交量激增比率: volume / volume_ma
    3. 同时满足「价格急跌 + 成交量激增」视为清算事件
    4. 清算事件后等待 cooldown 根 K 线，价格企稳后反向入场
    5. 设置最大持仓周期，防止在持续下跌中套牢
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class LiquidationHuntingStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Liquidation Hunting",
            description="Detect liquidation cascades and trade the subsequent mean-reversion bounce",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "accel_threshold": trial.suggest_float("accel_threshold", 0.005, 0.03),
            "vol_surge_mult": trial.suggest_float("vol_surge_mult", 2.0, 5.0),
            "vol_ma_window": trial.suggest_int("vol_ma_window", 10, 40),
            "cooldown": trial.suggest_int("cooldown", 1, 5),
            "hold_period": trial.suggest_int("hold_period", 3, 15),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        accel_thresh = params["accel_threshold"]
        vol_surge = params["vol_surge_mult"]
        vol_ma_w = params["vol_ma_window"]
        cooldown = params["cooldown"]
        hold_period = params["hold_period"]

        returns = df["close"].pct_change()
        acceleration = returns.diff()  # 二阶导
        vol_ma = df["volume"].rolling(vol_ma_w).mean()
        vol_ratio = df["volume"] / vol_ma.replace(0, np.nan)

        position = pd.Series(0.0, index=df.index)
        bars_in_trade = 0
        cooldown_counter = 0
        pos = 0.0
        last_event_dir = 0

        for i in range(vol_ma_w + 2, len(df)):
            acc = acceleration.iloc[i]
            vr = vol_ratio.iloc[i]

            if np.isnan(acc) or np.isnan(vr):
                position.iloc[i] = pos
                continue

            # 检测清算事件
            if abs(acc) > accel_thresh and vr > vol_surge:
                last_event_dir = -1 if acc < 0 else 1  # 下跌清算 / 上涨清算
                cooldown_counter = cooldown
                pos = 0.0

            # 冷却倒计时
            if cooldown_counter > 0:
                cooldown_counter -= 1
                if cooldown_counter == 0:
                    # 清算结束，反向入场
                    pos = -last_event_dir * 1.0
                    bars_in_trade = 0
                position.iloc[i] = pos
                continue

            # 持仓计时
            if pos != 0.0:
                bars_in_trade += 1
                if bars_in_trade >= hold_period:
                    pos = 0.0
                    bars_in_trade = 0

            position.iloc[i] = pos

        daily_return = df["close"].pct_change()
        strategy_return = (position.shift(1) * daily_return).fillna(0.0)
        return pd.Series(strategy_return, index=df.index)


STRATEGY_REGISTRY.register("liquidation_hunting", LiquidationHuntingStrategy())
