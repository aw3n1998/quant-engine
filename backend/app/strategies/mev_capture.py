# backend/app/strategies/mev_capture.py
"""
MEV Capture 策略

核心思想:
    MEV (Maximal Extractable Value) 是 DeFi 中矿工/验证者可提取的额外价值，
    主要来源于套利、清算和三明治攻击。高 MEV 活动通常伴随链上拥堵和价格波动。
    本策略将链上 MEV 分数作为波动率先行指标:
    - 高 MEV 分数预示即将到来的价格剧烈波动
    - 结合价格趋势方向建立顺势仓位

量化逻辑:
    1. 对 onchain_mev_score 进行滚动均值平滑
    2. 计算 MEV 分数的滚动百分位排名
    3. 当 MEV 百分位 > high_pct 时，表示链上活动异常活跃
    4. 在高 MEV 环境下，依据短期动量方向入场
    5. 低 MEV 环境下减仓或观望
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY
from app.utils.friction import apply_friction_costs


class MEVCaptureStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="MEV Capture",
            description="Use on-chain MEV score as a volatility leading indicator for directional bets",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "mev_smooth": trial.suggest_int("mev_smooth", 3, 15),
            "rank_window": trial.suggest_int("rank_window", 30, 120),
            "high_pct": trial.suggest_float("high_pct", 0.7, 0.95),
            "momentum_period": trial.suggest_int("momentum_period", 3, 15),
            "position_scale": trial.suggest_float("position_scale", 0.5, 1.0),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        mev_smooth = params["mev_smooth"]
        rank_window = params["rank_window"]
        high_pct = params["high_pct"]
        mom_period = params["momentum_period"]
        scale = params["position_scale"]

        # ── 降级检测：真实 Binance 数据无链上 MEV 字段时切换为 ATR 波动率突破策略 ──
        # 用 K 线振幅百分位替代 MEV 百分位，参数含义保持一致，Bayesian/GA 调参无感知
        if df["onchain_mev_score"].abs().sum() < 1e-10:
            high_col  = df["high"].rolling(mev_smooth).max()
            low_col   = df["low"].rolling(mev_smooth).min()
            atr_proxy = (high_col - low_col) / df["close"].replace(0, np.nan)
            atr_rank  = atr_proxy.rolling(rank_window).rank(pct=True)
            momentum  = df["close"].pct_change(mom_period)

            position = pd.Series(0.0, index=df.index)
            for i in range(rank_window, len(df)):
                rank_val = atr_rank.iloc[i]
                mom_val  = momentum.iloc[i]
                if np.isnan(rank_val) or np.isnan(mom_val):
                    continue
                if rank_val > high_pct:
                    position.iloc[i] = scale if mom_val > 0 else -scale

            return apply_friction_costs(position, df)

        mev = df["onchain_mev_score"].rolling(mev_smooth).mean()

        # 滚动百分位排名
        mev_rank = mev.rolling(rank_window).rank(pct=True)

        # 短期动量
        momentum = df["close"].pct_change(mom_period)

        position = pd.Series(0.0, index=df.index)
        for i in range(rank_window, len(df)):
            rank_val = mev_rank.iloc[i]
            mom_val = momentum.iloc[i]

            if np.isnan(rank_val) or np.isnan(mom_val):
                continue

            if rank_val > high_pct:
                # 高 MEV 活跃期: 顺动量方向入场
                if mom_val > 0:
                    position.iloc[i] = scale
                elif mom_val < 0:
                    position.iloc[i] = -scale
            else:
                # 低 MEV 期: 维持小仓位或观望
                position.iloc[i] = 0.0

        return apply_friction_costs(position, df)


STRATEGY_REGISTRY.register("mev_capture", MEVCaptureStrategy())
