# backend/app/utils/metrics.py
"""
量化绩效指标计算模块

提供标准化的量化绩效指标函数，包括:
- Sharpe Ratio (年化夏普比率)
- Calmar Ratio (年化收益 / 最大回撤)
- Maximum Drawdown (最大回撤)
- Annual Return (年化收益率)
- Equity Curve (净值曲线)

所有函数接受 pd.Series (每日收益率序列) 作为输入。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def annual_return(daily_returns: pd.Series) -> float:
    """
    计算年化收益率 (复利)
    annual_return = (cumulative_return) ^ (252 / n) - 1
    """
    total = (1 + daily_returns).prod()
    n = len(daily_returns)
    if n == 0 or total <= 0:
        return 0.0
    return float(total ** (TRADING_DAYS_PER_YEAR / n) - 1)


def max_drawdown(daily_returns: pd.Series) -> float:
    """
    计算最大回撤
    返回正数表示最大损失比例 (例如 0.25 表示 25% 回撤)
    """
    equity = (1 + daily_returns).cumprod()
    peak = equity.cummax()
    drawdown = (peak - equity) / peak
    mdd = drawdown.max()
    return float(mdd) if not np.isnan(mdd) else 0.0


def sharpe_ratio(
    daily_returns: pd.Series, risk_free_rate: float = 0.0
) -> float:
    """
    计算年化夏普比率
    Sharpe = (mean_daily_return - rf_daily) / std_daily * sqrt(252)
    """
    if len(daily_returns) < 2:
        return 0.0
    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = daily_returns - rf_daily
    std = excess.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR))


def calmar_ratio(daily_returns: pd.Series) -> float:
    """
    计算 Calmar Ratio = 年化收益率 / 最大回撤
    """
    ar = annual_return(daily_returns)
    mdd = max_drawdown(daily_returns)
    if mdd == 0:
        return 0.0
    return float(ar / mdd)


def equity_curve(daily_returns: pd.Series) -> list[float]:
    """
    计算净值曲线 (从 1.0 开始)
    返回 list[float] 便于 JSON 序列化
    """
    curve = (1 + daily_returns).cumprod()
    return curve.tolist()


def compute_all_metrics(daily_returns: pd.Series) -> dict:
    """
    一次性计算所有核心绩效指标
    返回字典，与 EngineResult 数据结构对齐
    """
    return {
        "sharpe": sharpe_ratio(daily_returns),
        "calmar": calmar_ratio(daily_returns),
        "max_drawdown": max_drawdown(daily_returns),
        "annual_return": annual_return(daily_returns),
        "equity_curve": equity_curve(daily_returns),
    }
