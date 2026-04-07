# backend/app/strategies/macro_capital_flow.py
"""
Macro Capital Flow 策略

核心思想:
    宏观资金流向决定了加密市场的中长期趋势。
    本策略综合多维宏观信号:
    - 资金费率趋势 (funding_rate 均线方向) 反映杠杆偏好
    - 成交量趋势 (volume 均线方向) 反映市场参与度
    - 情绪趋势 (nlp_sentiment 均线方向) 反映市场预期
    - 链上活跃度 (onchain_mev_score 均线方向) 反映链上资金流

    多维信号投票决定仓位方向和大小。

量化逻辑:
    1. 分别计算四个宏观指标的短期/长期均线
    2. 短期均线 > 长期均线 -> 该维度投票 +1，反之 -1
    3. 将四个投票加总，归一化至 [-1, 1] 作为仓位
    4. 投票一致性越高，仓位越大 (conviction scaling)
    5. 设置最小投票阈值，避免在信号矛盾时频繁交易
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class MacroCapitalFlowStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Macro Capital Flow",
            description="Multi-dimensional macro signal voting system combining funding, volume, sentiment, and on-chain activity",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "fast_window": trial.suggest_int("fast_window", 5, 20),
            "slow_window": trial.suggest_int("slow_window", 20, 60),
            "min_votes": trial.suggest_int("min_votes", 2, 4),
            "conviction_scale": trial.suggest_float("conviction_scale", 0.5, 1.0),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        fast_w = params["fast_window"]
        slow_w = params["slow_window"]
        min_votes = params["min_votes"]
        conv_scale = params["conviction_scale"]

        indicators = {
            "funding": df["funding_rate"],
            "volume": df["volume"],
            "sentiment": df["nlp_sentiment"],
            "onchain": df["onchain_mev_score"],
        }

        votes = pd.DataFrame(index=df.index)
        for name, series in indicators.items():
            fast_ma = series.rolling(fast_w).mean()
            slow_ma = series.rolling(slow_w).mean()
            votes[name] = np.sign(fast_ma - slow_ma)

        total_votes = votes.sum(axis=1)
        abs_votes = total_votes.abs()

        position = pd.Series(0.0, index=df.index)
        for i in range(slow_w, len(df)):
            v = total_votes.iloc[i]
            av = abs_votes.iloc[i]

            if np.isnan(v):
                continue

            if av >= min_votes:
                # 投票一致性越高，仓位越大
                position.iloc[i] = np.sign(v) * (av / 4.0) * conv_scale
            else:
                position.iloc[i] = 0.0

        position = position.clip(-1, 1)

        daily_return = df["close"].pct_change()
        strategy_return = (position.shift(1) * daily_return).fillna(0.0)
        return pd.Series(strategy_return, index=df.index)


STRATEGY_REGISTRY.register("macro_capital_flow", MacroCapitalFlowStrategy())
