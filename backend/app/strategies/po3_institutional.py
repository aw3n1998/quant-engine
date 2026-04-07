# backend/app/strategies/po3_institutional.py
"""
PO3 (Power of Three) Institutional 策略

核心思想:
    ICT (Inner Circle Trader) 方法论中的 PO3 模型认为，
    机构资金在每个交易周期内遵循三阶段运动:
    1. Accumulation (蓄力): 窄幅震荡，机构建仓
    2. Manipulation (诱骗): 假突破清除散户止损
    3. Distribution (分配): 真正的趋势方向展开

    策略通过识别低波动蓄力阶段后的假突破来判断真正方向。

量化逻辑:
    1. 计算滚动波动率 (ATR / close)，识别低波动蓄力区间
    2. 检测蓄力后的价格突破 (高/低点突破)
    3. 如果突破后快速回撤 (假突破)，则反向入场
    4. 如果突破后继续扩展 (真突破)，则顺向入场
    5. 使用蓄力区间的高低点作为止损参考
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class PO3InstitutionalStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="PO3 Institutional",
            description="ICT Power of Three model detecting accumulation, manipulation, and distribution phases",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "accum_window": trial.suggest_int("accum_window", 10, 40),
            "vol_percentile": trial.suggest_float("vol_percentile", 0.1, 0.4),
            "breakout_mult": trial.suggest_float("breakout_mult", 0.5, 2.0),
            "reversal_bars": trial.suggest_int("reversal_bars", 1, 5),
            "atr_period": trial.suggest_int("atr_period", 10, 30),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        accum_w = params["accum_window"]
        vol_pct = params["vol_percentile"]
        brk_mult = params["breakout_mult"]
        rev_bars = params["reversal_bars"]
        atr_period = params["atr_period"]

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # ATR 归一化为波动率指标
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(atr_period).mean()
        norm_vol = atr / close

        # 波动率阈值: 历史分位数
        vol_threshold = norm_vol.rolling(accum_w * 3).quantile(vol_pct)

        # 蓄力阶段: 波动率低于阈值
        is_accumulation = norm_vol < vol_threshold

        # 蓄力区间高低点
        accum_high = high.rolling(accum_w).max()
        accum_low = low.rolling(accum_w).min()
        accum_range = accum_high - accum_low
        accum_range = accum_range.replace(0, np.nan)

        position = pd.Series(0.0, index=df.index)
        pos = 0.0

        for i in range(accum_w + rev_bars, len(df)):
            if not is_accumulation.iloc[i - rev_bars]:
                position.iloc[i] = pos
                continue

            # 检测突破方向
            broke_up = close.iloc[i] > accum_high.iloc[i - 1] + brk_mult * atr.iloc[i]
            broke_down = close.iloc[i] < accum_low.iloc[i - 1] - brk_mult * atr.iloc[i]

            if broke_up:
                # 检查是否为假突破 (快速回撤)
                if i + rev_bars < len(df):
                    future_min = close.iloc[i:i + rev_bars].min()
                    if future_min < accum_high.iloc[i - 1]:
                        pos = -1.0  # 假突破做空
                    else:
                        pos = 1.0   # 真突破做多
            elif broke_down:
                if i + rev_bars < len(df):
                    future_max = close.iloc[i:i + rev_bars].max()
                    if future_max > accum_low.iloc[i - 1]:
                        pos = 1.0   # 假突破做多
                    else:
                        pos = -1.0  # 真突破做空

            position.iloc[i] = pos

        daily_return = close.pct_change()
        strategy_return = (position.shift(1) * daily_return).fillna(0.0)
        return pd.Series(strategy_return, index=df.index)


STRATEGY_REGISTRY.register("po3_institutional", PO3InstitutionalStrategy())
