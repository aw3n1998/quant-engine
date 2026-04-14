"""
数学与时间序列处理工具模块

包含高级特征工程算法，如分数阶微分 (Fractional Differentiation) 等。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def get_weights_ffd(d: float, thres: float) -> np.ndarray:
    """
    计算分数阶微分 (Fixed-Width Window FracDiff) 的权重系数。
    权重 w_k = -w_{k-1} * (d - k + 1) / k
    
    :param d: 微分阶数 (0 < d < 1)
    :param thres: 权重截断阈值（当权重绝对值小于该阈值时截断，避免计算过长）
    :return: 权重数组 (w_0, w_1, ..., w_k)
    """
    w = [1.0]
    k = 1
    while True:
        w_ = -w[-1] / k * (d - k + 1)
        if abs(w_) < thres:
            break
        w.append(w_)
        k += 1
    return np.array(w[::-1]).reshape(-1, 1)


def fractional_diff(series: pd.Series, d: float = 0.4, thres: float = 1e-4) -> pd.Series:
    """
    对 pandas 时间序列进行分数阶微分处理。
    
    原理：
    传统的一阶差分（d=1）使非平稳的价格序列变得平稳，但完全丢失了记忆（历史趋势信息）。
    分数阶微分通过 0 < d < 1 的权重衰减，在达到 ADF 平稳性检验要求的同时，
    最大程度地保留了序列的长记忆性。
    
    :param series: 输入的时间序列（如价格序列）
    :param d: 微分阶数
    :param thres: 权重截断阈值，影响滚动窗口的长度
    :return: 分数阶微分后的 pandas Series
    """
    weights = get_weights_ffd(d, thres)
    width = len(weights)
    
    df = pd.DataFrame(series)
    df = df.ffill()
    df = df.dropna()
    
    # 使用 numpy.convolve 向量化计算
    arr = df.iloc[:, 0].values
    if len(arr) < width:
        # 数据量不足以计算，返回 NaN
        return pd.Series(np.nan, index=series.index)
        
    res = np.convolve(arr, weights.flatten(), mode='valid')
    
    # 填充前面的无效值为 NaN，保证返回长度一致
    res_pad = np.pad(res, (width - 1, 0), constant_values=np.nan)
    return pd.Series(res_pad, index=series.index)

