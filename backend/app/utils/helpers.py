# backend/app/utils/helpers.py
"""
通用辅助函数
"""
from __future__ import annotations

import numpy as np


def set_global_seed(seed: int = 42) -> None:
    """
    固定全局随机种子，确保可复现性
    """
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def clip_returns(returns, lower: float = -0.5, upper: float = 0.5):
    """
    裁剪极端收益率，防止单日收益异常
    """
    return np.clip(returns, lower, upper)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    安全除法，避免除零错误
    """
    if denominator == 0 or np.isnan(denominator):
        return default
    result = numerator / denominator
    return result if not np.isnan(result) else default
