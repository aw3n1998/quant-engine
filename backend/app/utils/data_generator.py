# backend/app/utils/data_generator.py
"""
合成数据生成器

生成包含合理统计特征的加密货币模拟数据，涵盖:
- OHLCV 基础价格数据 (使用几何布朗运动)
- funding_rate (均值回复的资金费率)
- ob_imbalance (订单簿不平衡)
- onchain_mev_score (链上 MEV 活跃度)
- nlp_sentiment (NLP 情绪分数)

所有随机过程使用固定种子，保证可复现。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def generate_synthetic_data(
    n_rows: int = 2000,
    seed: int = 42,
    timeframe: str = "1d",
    initial_price: float = 30000.0,
    annual_drift: float = 0.15,
    annual_volatility: float = 0.80,
) -> pd.DataFrame:
    """
    生成合成加密货币数据

    Parameters
    ----------
    n_rows : int
        数据行数
    seed : int
        随机种子
    timeframe : str
        时间框架 (1d, 1h, etc.)
    initial_price : float
        初始价格
    annual_drift : float
        年化漂移率
    annual_volatility : float
        年化波动率
    """
    from app.utils.metrics import _get_bars_per_year
    bpy = _get_bars_per_year(timeframe)
    dt = 1.0 / bpy

    rng = np.random.default_rng(seed)

    # --- 几何布朗运动生成 close 价格序列 ---
    # 修正：根据 dt 缩放漂移和波动
    step_drift = (annual_drift - 0.5 * annual_volatility ** 2) * dt
    step_vol = annual_volatility * np.sqrt(dt)

    log_returns = step_drift + step_vol * rng.standard_normal(n_rows)
    log_prices = np.log(initial_price) + np.cumsum(log_returns)
    close = np.exp(log_prices)

    # --- 从 close 构造 OHLC ---
    # 单根 K 线波动范围: 约 0.5% - 2% (随 timeframe 缩放)
    range_scale = 0.04 * np.sqrt(365.0 / bpy)
    intraday_range = close * rng.uniform(range_scale * 0.5, range_scale, n_rows)
    high = close + intraday_range * rng.uniform(0.3, 0.7, n_rows)
    low = close - intraday_range * rng.uniform(0.3, 0.7, n_rows)
    low = np.maximum(low, close * 0.9)

    # open: 前一根 close 加微小偏移
    open_prices = np.roll(close, 1) * (1 + rng.normal(0, step_vol * 0.1, n_rows))
    open_prices[0] = initial_price

    # 确保 high >= max(open, close), low <= min(open, close)
    high = np.maximum(high, np.maximum(open_prices, close))
    low = np.minimum(low, np.minimum(open_prices, close))

    # --- 成交量 ---
    base_volume = rng.lognormal(mean=18.0, sigma=0.5, size=n_rows)
    vol_multiplier = 1.0 + 5.0 * np.abs(log_returns)
    volume = base_volume * vol_multiplier

    # --- 资金费率 (OU 过程) ---
    funding_rate = np.zeros(n_rows)
    fr_mean = 0.0001
    fr_speed = 0.05
    fr_vol = 0.0003
    funding_rate[0] = fr_mean
    for i in range(1, n_rows):
        funding_rate[i] = (
            funding_rate[i - 1]
            + fr_speed * (fr_mean - funding_rate[i - 1])
            + fr_vol * rng.standard_normal()
        )

    # --- 订单簿不平衡 ---
    ob_imbalance = np.zeros(n_rows)
    ob_imbalance[0] = rng.standard_normal() * 0.3
    for i in range(1, n_rows):
        ob_imbalance[i] = (
            0.7 * ob_imbalance[i - 1]
            + 0.3 * rng.standard_normal()
            + 0.2 * log_returns[i] / (step_vol + 1e-9)
        )

    # --- 链上 MEV 分数 ---
    mev_base = rng.exponential(scale=0.3, size=n_rows)
    volatility_spike = np.abs(log_returns) > 2 * step_vol
    mev_spike = volatility_spike.astype(float) * rng.exponential(scale=1.5, size=n_rows)
    onchain_mev_score = mev_base + mev_spike

    # --- NLP 情绪分数 ---
    nlp_sentiment = np.zeros(n_rows)
    nlp_sentiment[0] = 0.0
    for i in range(1, n_rows):
        nlp_sentiment[i] = (
            0.85 * nlp_sentiment[i - 1]
            + 0.3 * log_returns[i] / (step_vol + 1e-9)
            + 0.15 * rng.standard_normal()
        )

    # --- 构造 DataFrame ---
    # 频率映射
    freq_map = {"1d": "D", "4h": "4h", "1h": "h", "30m": "30min", "15m": "15min", "5m": "5min"}
    freq = freq_map.get(timeframe, "D")
    
    dates = pd.date_range(start="2022-01-01", periods=n_rows, freq=freq)
    df = pd.DataFrame(
        {
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "funding_rate": funding_rate,
            "ob_imbalance": ob_imbalance,
            "onchain_mev_score": onchain_mev_score,
            "nlp_sentiment": nlp_sentiment,
        },
        index=dates,
    )
    df.index.name = "datetime"

    return df
