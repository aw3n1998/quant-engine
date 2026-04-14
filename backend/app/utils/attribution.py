"""
因子归因分析模块 (Factor Attribution / Brinson Model) - Phase 7
计算策略的 Beta、Alpha 以及市场相关性。
"""
import numpy as np
import pandas as pd

def calculate_alpha_beta(strategy_returns: pd.Series, benchmark_returns: pd.Series, risk_free_rate: float = 0.0) -> dict:
    """
    计算策略相对于基准（通常是 BTC）的 Alpha 和 Beta。
    """
    df = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
    df.columns = ["strategy", "benchmark"]
    
    if len(df) < 2:
        return {"alpha": 0.0, "beta": 0.0}
        
    cov = df.cov().iloc[0, 1]
    var_bench = df["benchmark"].var()
    
    beta = cov / var_bench if var_bench > 0 else 0.0
    
    # 年化收益 (假设 daily bars)
    ann_strat = df["strategy"].mean() * 365
    ann_bench = df["benchmark"].mean() * 365
    
    alpha = ann_strat - (risk_free_rate + beta * (ann_bench - risk_free_rate))
    
    return {"alpha": alpha, "beta": beta}

def rolling_correlation(strategy_returns: pd.Series, benchmark_returns: pd.Series, window: int = 30) -> pd.Series:
    """
    计算策略与基准的滚动相关系数。用于监控策略是否过度依赖市场大势。
    """
    df = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
    df.columns = ["strategy", "benchmark"]
    return df["strategy"].rolling(window=window).corr(df["benchmark"]).fillna(0.0)
