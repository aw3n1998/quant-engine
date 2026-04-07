# backend/app/strategies/liquidity_hedge_mining.py
"""
Liquidity Hedge Mining 策略

核心思想:
    DeFi 流动性挖矿的收益与市场波动率和资金费率密切相关。
    本策略模拟「流动性提供 + 对冲」的思路:
    - 基础收益来自资金费率 (funding_rate) 的持续收取
    - 使用价格趋势对冲无常损失风险
    - 在高波动环境下缩减流动性敞口

量化逻辑:
    1. 计算资金费率的滚动累计收益
    2. 计算已实现波动率作为风险指标
    3. 低波动 + 正资金费率 -> 提供流动性 (等效做多)
    4. 低波动 + 负资金费率 -> 反向流动性 (等效做空)
    5. 高波动 -> 缩减仓位，以对冲系数缩放
    6. 总收益 = 方向性收益 * hedge_ratio + 资金费率收益
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class LiquidityHedgeMiningStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Liquidity Hedge Mining",
            description="Simulate DeFi liquidity provision with dynamic hedging based on volatility and funding rate",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "vol_window": trial.suggest_int("vol_window", 10, 40),
            "vol_high_pct": trial.suggest_float("vol_high_pct", 0.6, 0.9),
            "hedge_ratio": trial.suggest_float("hedge_ratio", 0.3, 0.8),
            "fr_weight": trial.suggest_float("fr_weight", 0.5, 3.0),
            "trend_window": trial.suggest_int("trend_window", 10, 40),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        vol_window = params["vol_window"]
        vol_high_pct = params["vol_high_pct"]
        hedge_ratio = params["hedge_ratio"]
        fr_weight = params["fr_weight"]
        trend_window = params["trend_window"]

        returns = df["close"].pct_change()
        realized_vol = returns.rolling(vol_window).std()
        vol_threshold = realized_vol.rolling(vol_window * 3).quantile(vol_high_pct)

        fr = df["funding_rate"]
        trend_sma = df["close"].rolling(trend_window).mean()
        trend_dir = np.sign(df["close"] - trend_sma)

        strategy_return = pd.Series(0.0, index=df.index)

        for i in range(max(vol_window * 3, trend_window), len(df)):
            vol = realized_vol.iloc[i]
            vol_th = vol_threshold.iloc[i]
            funding = fr.iloc[i]
            t_dir = trend_dir.iloc[i]
            daily_ret = returns.iloc[i]

            if np.isnan(vol) or np.isnan(vol_th) or np.isnan(daily_ret):
                continue

            # 波动率分层: 高波动缩减仓位
            if vol > vol_th:
                scale = hedge_ratio
            else:
                scale = 1.0

            # 方向: 跟随资金费率信号
            if funding > 0:
                direction = 1.0  # 正费率，做多收取
            elif funding < 0:
                direction = -1.0
            else:
                direction = t_dir

            directional_pnl = direction * daily_ret * scale
            funding_pnl = abs(funding) * fr_weight * 0.01  # 资金费率收益缩放

            strategy_return.iloc[i] = directional_pnl + funding_pnl

        return pd.Series(strategy_return, index=df.index)


STRATEGY_REGISTRY.register("liquidity_hedge_mining", LiquidityHedgeMiningStrategy())
