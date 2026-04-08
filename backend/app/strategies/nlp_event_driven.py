# backend/app/strategies/nlp_event_driven.py
"""
NLP Event Driven 策略

核心思想:
    市场情绪驱动短期价格波动。NLP 情绪分数 (nlp_sentiment) 量化了
    新闻、社交媒体等文本数据中的多空情绪。本策略利用情绪分数的
    突变和极端值来捕捉事件驱动的价格运动。

量化逻辑:
    1. 计算 nlp_sentiment 的滚动均值和标准差
    2. 计算情绪变化速率 (sentiment delta): 当前值 - 滚动均值
    3. 情绪突变 (delta > threshold) 且为正面 -> 做多
    4. 情绪突变 (delta < -threshold) 且为负面 -> 做空
    5. 结合成交量放大确认: 事件驱动应伴随成交量异常
    6. 设置衰减窗口: 情绪信号随时间衰减，避免持仓过久
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class NLPEventDrivenStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="NLP Event Driven",
            description="Capture sentiment-driven price moves using NLP sentiment spikes with volume confirmation",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "sent_window": trial.suggest_int("sent_window", 5, 30),
            "delta_threshold": trial.suggest_float("delta_threshold", 0.5, 2.5),
            "vol_spike_mult": trial.suggest_float("vol_spike_mult", 1.2, 3.0),
            "decay_period": trial.suggest_int("decay_period", 3, 15),
            "vol_ma_window": trial.suggest_int("vol_ma_window", 10, 40),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        sent_w = params["sent_window"]
        delta_thresh = params["delta_threshold"]
        vol_spike = params["vol_spike_mult"]
        decay = params["decay_period"]
        vol_ma_w = params["vol_ma_window"]

        # ── 降级检测：真实 Binance 数据无 NLP 情绪字段时切换为成交量异常 + 价格突破策略 ──
        # 用成交量 Z-score 替代情绪 Z-score，vol_spike_mult / decay 等参数语义不变
        if df["nlp_sentiment"].abs().sum() < 1e-10:
            vol_ma  = df["volume"].rolling(vol_ma_w).mean()
            vol_std = df["volume"].rolling(vol_ma_w).std().replace(0, np.nan)
            vol_z   = (df["volume"] - vol_ma) / vol_std
            price_chg = df["close"].pct_change()

            position = pd.Series(0.0, index=df.index)
            pos = 0.0
            bars_held = 0
            for i in range(vol_ma_w, len(df)):
                vz = vol_z.iloc[i]
                pc = price_chg.iloc[i]
                if np.isnan(vz) or np.isnan(pc):
                    position.iloc[i] = pos
                    continue
                bars_held += 1
                # 成交量突破 delta_threshold 倍标准差时视为事件触发
                if vz > delta_thresh:
                    pos = 1.0 if pc > 0 else -1.0
                    bars_held = 0
                if bars_held > decay:
                    pos = 0.0
                position.iloc[i] = pos

            daily_return = df["close"].pct_change()
            return (position.shift(1) * daily_return).fillna(0.0)

        sentiment = df["nlp_sentiment"]
        sent_ma = sentiment.rolling(sent_w).mean()
        sent_std = sentiment.rolling(sent_w).std().replace(0, np.nan)
        sent_delta = (sentiment - sent_ma) / sent_std

        vol_ma = df["volume"].rolling(vol_ma_w).mean()
        vol_confirm = df["volume"] > vol_spike * vol_ma

        position = pd.Series(0.0, index=df.index)
        bars_since_signal = 0
        pos = 0.0

        for i in range(max(sent_w, vol_ma_w), len(df)):
            delta = sent_delta.iloc[i]
            if np.isnan(delta):
                position.iloc[i] = pos
                continue

            bars_since_signal += 1

            if delta > delta_thresh and vol_confirm.iloc[i]:
                pos = 1.0
                bars_since_signal = 0
            elif delta < -delta_thresh and vol_confirm.iloc[i]:
                pos = -1.0
                bars_since_signal = 0

            # 情绪信号衰减
            if bars_since_signal > decay:
                pos = 0.0

            position.iloc[i] = pos

        daily_return = df["close"].pct_change()
        strategy_return = (position.shift(1) * daily_return).fillna(0.0)
        return pd.Series(strategy_return, index=df.index)


STRATEGY_REGISTRY.register("nlp_event_driven", NLPEventDrivenStrategy())
