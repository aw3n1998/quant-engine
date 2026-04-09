# backend/app/utils/metrics.py
"""
量化绩效指标计算模块

提供标准化的量化绩效指标函数，包括:
- Sharpe Ratio (年化夏普比率)
- Calmar Ratio (年化收益 / 最大回撤)
- Maximum Drawdown (最大回撤)
- Annual Return (年化收益率)
- Equity Curve (净值曲线)

注意：所有函数现在支持 bars_per_year 参数，以适配不同时间框架数据。
加密货币市场 365天×24小时 不间断运行，年化因子与传统股市不同。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# -----------------------------------------------------------------------
# 【年化因子映射】
# 加密货币市场 365天 × 24小时 不间断运行，不同时间框架每年K线数不同。
# 使用错误的年化因子会导致 Sharpe/Calmar 被严重低估或高估。
# 例如：用 1h 数据但 bars_per_year=252（日线），
#        Sharpe 会被低估约 5.9 倍（√8760/√252 ≈ 5.9）。
# -----------------------------------------------------------------------
BARS_PER_YEAR: dict[str, int] = {
    "1d":  365,
    "4h":  365 * 6,    # 2190
    "1h":  365 * 24,   # 8760
    "30m": 365 * 48,   # 17520
    "15m": 365 * 96,   # 35040
    "5m":  365 * 288,  # 105120
}

# 默认使用日线（向后兼容）
DEFAULT_BARS_PER_YEAR = 365


def _get_bars_per_year(timeframe: str) -> int:
    return BARS_PER_YEAR.get(timeframe, DEFAULT_BARS_PER_YEAR)


def annual_return(returns: pd.Series, timeframe: str = "1d") -> float:
    """
    计算年化收益率 (复利)
    annual_return = total_return ^ (bars_per_year / n) - 1
    """
    total = (1 + returns).prod()
    n = len(returns)
    if n == 0 or total <= 0:
        return 0.0
    bpy = _get_bars_per_year(timeframe)
    return float(total ** (bpy / n) - 1)


def max_drawdown(returns: pd.Series) -> float:
    """
    计算最大回撤
    返回正数表示最大损失比例 (例如 0.25 表示 25% 回撤)
    """
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    drawdown = (peak - equity) / peak
    mdd = drawdown.max()
    return float(mdd) if not np.isnan(mdd) else 0.0


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, timeframe: str = "1d") -> float:
    """
    计算年化夏普比率
    Sharpe = (mean_return - rf_per_bar) / std_return * sqrt(bars_per_year)
    """
    if len(returns) < 2:
        return 0.0
    bpy = _get_bars_per_year(timeframe)
    rf_per_bar = risk_free_rate / bpy
    excess = returns - rf_per_bar
    std = excess.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(bpy))


def calmar_ratio(returns: pd.Series, timeframe: str = "1d") -> float:
    """
    计算 Calmar Ratio = 年化收益率 / 最大回撤

    修复：当策略无交易信号时返回 -inf 而非 0，
    避免 Optuna/GA 误将"零活跃策略"认定为最优解。
    """
    # 无交易信号检测
    if returns.abs().sum() < 1e-10:
        return float('-inf')

    ar = annual_return(returns, timeframe=timeframe)
    mdd = max_drawdown(returns)
    if mdd == 0:
        # 零回撤 = 完美策略，直接返回年化收益本身（避免÷0且不惩罚完美结果）
        return float(ar) if ar > 0 else 0.0
    return float(ar / mdd)


def equity_curve(returns: pd.Series) -> list[float]:
    """
    计算净值曲线 (从 1.0 开始)
    返回 list[float] 便于 JSON 序列化
    """
    curve = (1 + returns).cumprod()
    return curve.tolist()


def safe_mean(values: list[float]) -> float:
    """安全均值：过滤 -inf/nan，全部无效返回 -10.0"""
    finite = [v for v in values if np.isfinite(v)]
    return float(np.mean(finite)) if finite else -10.0


def compute_all_metrics(returns: pd.Series, timeframe: str = "1d") -> dict:
    """
    一次性计算所有核心绩效指标
    支持 timeframe 参数以正确年化
    """
    return {
        "sharpe":        sharpe_ratio(returns, timeframe=timeframe),
        "calmar":        calmar_ratio(returns, timeframe=timeframe),
        "max_drawdown":  max_drawdown(returns),
        "annual_return": annual_return(returns, timeframe=timeframe),
        "equity_curve":  equity_curve(returns),
    }
