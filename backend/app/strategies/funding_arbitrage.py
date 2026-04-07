# backend/app/strategies/funding_arbitrage.py
"""
Funding Rate Arbitrage 策略

核心思想:
    加密货币永续合约的资金费率反映多空力量对比。
    当资金费率极端偏高时，做多方支付费用给做空方 -- 此时市场过度看多，
    反转概率增大，策略做空现货 (或等价做空)。
    当资金费率极端偏低 (负值) 时，做空方支付费用，策略做多。
    本质上是一种均值回归交易。

量化逻辑:
    1. 计算资金费率的滚动 Z-score
    2. Z-score > upper_z 时做空 (资金费率过高，市场过热)
    3. Z-score < -lower_z 时做多 (资金费率过低，市场过冷)
    4. Z-score 回归 0 附近时平仓
    5. 结合价格动量过滤极端单边行情
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class FundingArbitrageStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Funding Rate Arbitrage",
            description="Mean-reversion strategy based on funding rate Z-score extremes",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "z_window": trial.suggest_int("z_window", 20, 100),
            "upper_z": trial.suggest_float("upper_z", 1.0, 3.0),
            "lower_z": trial.suggest_float("lower_z", 1.0, 3.0),
            "exit_z": trial.suggest_float("exit_z", 0.0, 0.8),
            "momentum_filter": trial.suggest_int("momentum_filter", 5, 30),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        z_window = params["z_window"]
        upper_z = params["upper_z"]
        lower_z = params["lower_z"]
        exit_z = params["exit_z"]
        mom_period = params["momentum_filter"]

        fr = df["funding_rate"]
        fr_mean = fr.rolling(z_window).mean()
        fr_std = fr.rolling(z_window).std().replace(0, np.nan)
        z_score = (fr - fr_mean) / fr_std

        price_mom = df["close"].pct_change(mom_period)

        position = pd.Series(0.0, index=df.index)
        pos = 0.0
        for i in range(z_window, len(df)):
            z = z_score.iloc[i]
            mom = price_mom.iloc[i] if not np.isnan(price_mom.iloc[i]) else 0.0

            if z > upper_z and mom < 0.05:
                pos = -1.0
            elif z < -lower_z and mom > -0.05:
                pos = 1.0
            elif abs(z) < exit_z:
                pos = 0.0
            position.iloc[i] = pos

        daily_return = df["close"].pct_change()
        strategy_return = (position.shift(1) * daily_return).fillna(0.0)
        return pd.Series(strategy_return, index=df.index)


STRATEGY_REGISTRY.register("funding_arbitrage", FundingArbitrageStrategy())
