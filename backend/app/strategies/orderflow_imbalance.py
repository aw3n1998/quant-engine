# backend/app/strategies/orderflow_imbalance.py
"""
Order Flow Imbalance 策略

核心思想:
    订单流不平衡反映了市场微观结构中买卖力量的非对称性。
    当买方压力显著大于卖方时，价格倾向于上涨，反之亦然。
    本策略使用合成的订单簿不平衡指标 (ob_imbalance) 作为核心信号源，
    结合价格趋势过滤器避免在震荡市中频繁交易。

量化逻辑:
    1. 对 ob_imbalance 进行滚动平滑，减少噪声
    2. 计算平滑后不平衡指标的 Z-score
    3. Z-score > entry_z 表示买方极度强势，做多
    4. Z-score < -entry_z 表示卖方极度强势，做空
    5. 叠加短期均线趋势过滤: 仅在趋势方向一致时入场
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class OrderFlowImbalanceStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Order Flow Imbalance",
            description="Exploit order book imbalance extremes with trend alignment filter",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "smooth_window": trial.suggest_int("smooth_window", 3, 20),
            "z_window": trial.suggest_int("z_window", 20, 80),
            "entry_z": trial.suggest_float("entry_z", 1.0, 3.0),
            "exit_z": trial.suggest_float("exit_z", 0.0, 1.0),
            "trend_ma": trial.suggest_int("trend_ma", 10, 50),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        smooth_w = params["smooth_window"]
        z_window = params["z_window"]
        entry_z = params["entry_z"]
        exit_z = params["exit_z"]
        trend_ma = params["trend_ma"]

        ob = df["ob_imbalance"].rolling(smooth_w).mean()
        ob_mean = ob.rolling(z_window).mean()
        ob_std = ob.rolling(z_window).std().replace(0, np.nan)
        z_score = (ob - ob_mean) / ob_std

        # 趋势过滤: 短期均线方向
        sma = df["close"].rolling(trend_ma).mean()
        trend_up = df["close"] > sma
        trend_down = df["close"] < sma

        position = pd.Series(0.0, index=df.index)
        pos = 0.0
        for i in range(max(z_window, trend_ma), len(df)):
            z = z_score.iloc[i]
            if np.isnan(z):
                position.iloc[i] = pos
                continue

            if z > entry_z and trend_up.iloc[i]:
                pos = 1.0
            elif z < -entry_z and trend_down.iloc[i]:
                pos = -1.0
            elif abs(z) < exit_z:
                pos = 0.0
            position.iloc[i] = pos

        daily_return = df["close"].pct_change()
        strategy_return = (position.shift(1) * daily_return).fillna(0.0)
        return pd.Series(strategy_return, index=df.index)


STRATEGY_REGISTRY.register("orderflow_imbalance", OrderFlowImbalanceStrategy())
