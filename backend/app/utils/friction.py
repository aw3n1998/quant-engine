# backend/app/utils/friction.py
"""
真实摩擦成本模型 — 纯向量化实现
=====================================

消除策略回测中的"零成本陷阱"：
  - 每次换手（仓位变化）收取 Taker 手续费
  - 高波动市场自动加大 ATR 动态滑点
  - 全程无 Python for 循环，O(n) 时间复杂度

摩擦成本数学模型
-----------------

设 Δp_t = |position_t - position_{t-1}|   （换手量）

  ① 手续费（Taker 模型）：
       fee_t = Δp_t × taker_fee
       # Δp=1 (0→+1 单向开仓)   → 付 1 × taker_fee
       # Δp=2 (+1→-1 双向反手)  → 付 2 × taker_fee（关多+开空各1单位）

  ② ATR 动态滑点（市场冲击）：
       TR_t      = max(H_t − L_t, |H_t − C_{t-1}|, |L_t − C_{t-1}|)
       ATR_t     = rolling_mean(TR, window)
       ATR_pct_t = ATR_t / C_t                    （ATR 占收盘价的百分比）
       slippage_t = Δp_t × ATR_pct_t × slippage_mult

  ③ 净收益：
       gross_t = position_{t-1} × (C_t / C_{t-1} − 1)
       net_t   = gross_t − fee_t − slippage_t

典型参数参考（2024 主流 CEX）：
  Maker 手续费: 0.0002 (0.02%/单边, BN VIP0)
  Taker 手续费: 0.0005 (0.05%/单边, BN VIP0)
  ATR 滑点系数: 0.10 ≈ 主流大市值币，0.30 ≈ 山寨/流动性差时段
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def apply_friction_costs(
    position: pd.Series,
    df: pd.DataFrame,
    *,
    maker_fee: float = 0.0002,    # Maker 单边手续费 0.02%（挂单方，供参考）
    taker_fee: float = 0.0005,    # Taker 单边手续费 0.05%（吃单方，默认保守估计）
    slippage_mult: float = 0.10,  # 滑点系数：每单位换手消耗的 ATR 占价格的比例
    atr_window: int = 14,         # ATR 滚动窗口（K 线数）
) -> pd.Series:
    """
    向量化扣除手续费与 ATR 动态滑点，返回净收益序列。

    Parameters
    ----------
    position      : 仓位时序 (±1 做多/空, 0 空仓)，与 df 行数对齐
    df            : OHLCV DataFrame，至少含 'close'；有 'high'/'low' 时启用 ATR 滑点
    maker_fee     : Maker 单边手续费（当前逻辑使用 taker_fee，此参数供用户按需切换）
    taker_fee     : Taker 单边手续费（默认 0.05%，对应市价单场景）
    slippage_mult : ATR 滑点系数；0.10 = 每单位换手承受 10% ATR 的滑点损失
    atr_window    : True Range 滚动均值计算窗口

    Returns
    -------
    pd.Series — 与 df 索引对齐的净收益序列（已 fillna(0)）

    Notes
    -----
    实现细节（向量化关键点）：
      • position.diff().abs()  — O(n) 换手量，无循环
      • iloc[0] 手动设置首根建仓换手（diff() 首行为 NaN）
      • pd.concat([...]).max(axis=1) — 向量化 True Range
      • 所有中间量均为 pd.Series，保持索引对齐
    """
    close = df["close"]

    # ── 1. 毛收益（延迟1根，模拟"收盘决策，次日执行"）─────────────────
    gross = position.shift(1) * close.pct_change()

    # ── 2. 换手量（完全向量化，O(n)）────────────────────────────────────
    pos_delta = position.diff().abs()          # |pos[t] - pos[t-1]|
    pos_delta.iloc[0] = abs(position.iloc[0])  # 初始建仓：从 0 到 position[0]

    # ── 3. 手续费成本（Taker fee，单边，乘以换手量）──────────────────────
    # 若策略以 maker 单执行，可改为 maker_fee
    fee_cost = pos_delta * taker_fee

    # ── 4. ATR 动态滑点（市场冲击，向量化 True Range）───────────────────
    if {"high", "low"}.issubset(df.columns):
        prev_c = close.shift(1)
        # True Range = max(H-L, |H-prev_C|, |L-prev_C|)，三列向量化取最大
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - prev_c).abs(),
            (df["low"]  - prev_c).abs(),
        ], axis=1).max(axis=1)
        atr     = tr.rolling(atr_window, min_periods=1).mean()
        atr_pct = atr / close.replace(0.0, np.nan)   # ATR 占价格百分比
    else:
        # 无 H/L 时降级：用近期绝对收益率近似波动率
        atr_pct = close.pct_change().abs().rolling(atr_window, min_periods=1).mean()

    slippage_cost = pos_delta * atr_pct.fillna(0.0) * slippage_mult

    # ── 5. 净收益 = 毛收益 - 手续费 - 滑点 ──────────────────────────────
    return (gross - fee_cost - slippage_cost).fillna(0.0)
