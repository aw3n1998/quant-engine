"""
Numba 向量化技术指标 (Phase 8 Performance Optimization)
使用 JIT 编译大幅加速循环计算密集的指标（如 EMA, RMA, RSI）。
"""
import numpy as np
import pandas as pd
from numba import njit

@njit
def fast_ema(arr: np.ndarray, period: int) -> np.ndarray:
    """
    超高速 EMA 计算 (Numba JIT)
    比 pandas.ewm 提升数十倍性能。
    """
    res = np.empty_like(arr)
    res[0] = arr[0]
    alpha = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        res[i] = arr[i] * alpha + res[i-1] * (1 - alpha)
    return res

@njit
def fast_rsi(arr: np.ndarray, period: int) -> np.ndarray:
    """
    超高速 RSI 计算 (Numba JIT)
    """
    res = np.zeros_like(arr)
    gain = 0.0
    loss = 0.0
    
    # 预热
    for i in range(1, period + 1):
        if i >= len(arr):
            break
        change = arr[i] - arr[i-1]
        if change > 0:
            gain += change
        else:
            loss -= change
            
    gain /= period
    loss /= period
    
    if period < len(arr):
        if loss == 0:
            res[period] = 100.0
        else:
            rs = gain / loss
            res[period] = 100.0 - (100.0 / (1.0 + rs))
        
    alpha = 1.0 / period
    for i in range(period + 1, len(arr)):
        change = arr[i] - arr[i-1]
        if change > 0:
            gain = gain * (1 - alpha) + change * alpha
            loss = loss * (1 - alpha)
        else:
            gain = gain * (1 - alpha)
            loss = loss * (1 - alpha) - change * alpha
            
        if loss == 0:
            res[i] = 100.0
        else:
            rs = gain / loss
            res[i] = 100.0 - (100.0 / (1.0 + rs))
            
    return res

def get_fast_rsi(series: pd.Series, period: int) -> pd.Series:
    """
    给 Pandas Series 使用的封装。
    """
    arr = series.values
    if len(arr) <= period:
        return pd.Series(np.nan, index=series.index)
    res_arr = fast_rsi(arr, period)
    res_series = pd.Series(res_arr, index=series.index)
    res_series.iloc[:period] = np.nan
    return res_series
