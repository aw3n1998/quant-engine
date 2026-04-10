# backend/app/strategies/price_action_sr.py
"""
Price Action + Support/Resistance Strategy（支撑阻力反转策略）

核心思想:
    识别价格历史中的支撑/阻力区域，在价格触碰这些关键位时捕捉反转信号。

    支撑/阻力检测:
    1. 在过去 lookback 根K线中找出局部高点（两侧 local_window 根都低于它）→ 阻力位
    2. 找出局部低点（两侧 local_window 根都高于它）→ 支撑位
    3. 将距离 < zone_pct 的相近价位聚合为一个区域

    信号生成:
    - 价格接近支撑区（误差 < zone_pct）→ 做多
    - 价格接近阻力区（误差 < zone_pct）→ 做空
    - 需要 momentum_confirm 根K线的方向确认
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY
from app.utils.friction import apply_friction_costs


def _find_local_extrema(series: pd.Series, window: int) -> tuple[list[float], list[float]]:
    """找出序列中的局部最大值和最小值"""
    highs, lows = [], []
    vals = series.values
    n    = len(vals)
    for i in range(window, n - window):
        segment = vals[i - window: i + window + 1]
        if vals[i] == segment.max():
            highs.append(float(vals[i]))
        if vals[i] == segment.min():
            lows.append(float(vals[i]))
    return highs, lows


def _cluster_levels(levels: list[float], zone_pct: float) -> list[float]:
    """将相近价位（距离 < zone_pct）聚合为一个区域中心"""
    if not levels:
        return []
    sorted_levels = sorted(levels)
    clusters: list[float] = []
    current_cluster = [sorted_levels[0]]
    for lv in sorted_levels[1:]:
        ref = current_cluster[-1]
        if abs(lv - ref) / (ref + 1e-9) < zone_pct:
            current_cluster.append(lv)
        else:
            clusters.append(float(np.mean(current_cluster)))
            current_cluster = [lv]
    clusters.append(float(np.mean(current_cluster)))
    return clusters


class PriceActionSrStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Price Action S/R",
            description="Auto-detects support/resistance zones from local extrema, trades reversals at key levels",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "lookback":          trial.suggest_int("lookback",          20, 80),
            "local_window":      trial.suggest_int("local_window",       3,  8),
            "zone_pct":          trial.suggest_float("zone_pct",       0.005, 0.025),
            "momentum_confirm":  trial.suggest_int("momentum_confirm",   2,  8),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        lookback = params["lookback"]
        lw       = params["local_window"]
        zone_pct = params["zone_pct"]
        confirm  = params["momentum_confirm"]

        close     = df["close"]
        daily_ret = close.pct_change()
        position  = pd.Series(0.0, index=df.index)

        warmup = lookback + lw + confirm + 5

        pos            = 0.0
        confirm_count  = 0
        pending_signal = 0.0  # 待确认方向

        for i in range(warmup, len(df)):
            # 用过去 lookback 根K线的局部高低点
            window_slice = close.iloc[i - lookback: i]
            highs, lows  = _find_local_extrema(window_slice, lw)
            resistances  = _cluster_levels(highs, zone_pct)
            supports     = _cluster_levels(lows,  zone_pct)

            cur = close.iloc[i]

            # 检测是否触碰区域
            near_support    = any(abs(cur - s) / (s + 1e-9) < zone_pct for s in supports)
            near_resistance = any(abs(cur - r) / (r + 1e-9) < zone_pct for r in resistances)

            if near_support and pending_signal == 0.0 and pos <= 0.0:
                pending_signal = 1.0
                confirm_count  = 0
            elif near_resistance and pending_signal == 0.0 and pos >= 0.0:
                pending_signal = -1.0
                confirm_count  = 0

            # 动量确认：需要连续 confirm 根同向K线
            if pending_signal != 0.0:
                last_ret = daily_ret.iloc[i]
                if np.sign(last_ret) == pending_signal:
                    confirm_count += 1
                else:
                    confirm_count = max(0, confirm_count - 1)

                if confirm_count >= confirm:
                    pos            = pending_signal
                    pending_signal = 0.0
                    confirm_count  = 0

            position.iloc[i] = pos

        return apply_friction_costs(position, df)


STRATEGY_REGISTRY.register("price_action_sr", PriceActionSrStrategy())
