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
    initial_price: float = 30000.0,
    annual_drift: float = 0.15,
    annual_volatility: float = 0.80,
) -> pd.DataFrame:
    """
    生成合成加密货币数据

    Parameters
    ----------
    n_rows : int
        数据行数 (天数)
    seed : int
        随机种子
    initial_price : float
        初始价格
    annual_drift : float
        年化漂移率
    annual_volatility : float
        年化波动率

    Returns
    -------
    pd.DataFrame
        索引为 datetime，包含以下列:
        open, high, low, close, volume,
        funding_rate, ob_imbalance, onchain_mev_score, nlp_sentiment
    """
    rng = np.random.default_rng(seed)

    # --- 几何布朗运动生成 close 价格序列 ---
    dt = 1.0 / 365.0
    daily_drift = (annual_drift - 0.5 * annual_volatility ** 2) * dt
    daily_vol = annual_volatility * np.sqrt(dt)

    log_returns = daily_drift + daily_vol * rng.standard_normal(n_rows)
    log_prices = np.log(initial_price) + np.cumsum(log_returns)
    close = np.exp(log_prices)

    # --- 从 close 构造 OHLC ---
    # 日内波动范围: 每日振幅约 2%-5%
    intraday_range = close * rng.uniform(0.01, 0.04, n_rows)
    high = close + intraday_range * rng.uniform(0.3, 0.7, n_rows)
    low = close - intraday_range * rng.uniform(0.3, 0.7, n_rows)
    low = np.maximum(low, close * 0.9)  # 防止极端负值

    # open: 前一日 close 加微小偏移 (模拟隔夜跳空)
    open_prices = np.roll(close, 1) * (1 + rng.normal(0, 0.005, n_rows))
    open_prices[0] = initial_price

    # 确保 high >= max(open, close), low <= min(open, close)
    high = np.maximum(high, np.maximum(open_prices, close))
    low = np.minimum(low, np.minimum(open_prices, close))

    # --- 成交量: 对数正态分布 + 与价格波动正相关 ---
    base_volume = rng.lognormal(mean=18.0, sigma=0.5, size=n_rows)
    vol_multiplier = 1.0 + 3.0 * np.abs(log_returns)
    volume = base_volume * vol_multiplier

    # --- 资金费率: 均值回复 OU 过程 ---
    funding_rate = np.zeros(n_rows)
    fr_mean = 0.0001  # 长期均值 (略正, 对应多头占优的常态)
    fr_speed = 0.05   # 回复速度
    fr_vol = 0.0003   # 波动率
    funding_rate[0] = fr_mean
    for i in range(1, n_rows):
        funding_rate[i] = (
            funding_rate[i - 1]
            + fr_speed * (fr_mean - funding_rate[i - 1])
            + fr_vol * rng.standard_normal()
        )

    # --- 订单簿不平衡: 均值为 0 的自相关序列 ---
    ob_imbalance = np.zeros(n_rows)
    ob_imbalance[0] = rng.standard_normal() * 0.3
    for i in range(1, n_rows):
        ob_imbalance[i] = (
            0.7 * ob_imbalance[i - 1]
            + 0.3 * rng.standard_normal()
            + 0.2 * log_returns[i] / daily_vol  # 与价格变动微弱相关
        )

    # --- 链上 MEV 分数: 非负, 偶尔出现高峰 ---
    mev_base = rng.exponential(scale=0.3, size=n_rows)
    # 在高波动日叠加 MEV 激增
    volatility_spike = np.abs(log_returns) > 2 * daily_vol
    mev_spike = volatility_spike.astype(float) * rng.exponential(scale=1.5, size=n_rows)
    onchain_mev_score = mev_base + mev_spike

    # --- NLP 情绪分数: 均值回复 + 与价格变动正相关 ---
    nlp_sentiment = np.zeros(n_rows)
    nlp_sentiment[0] = 0.0
    for i in range(1, n_rows):
        nlp_sentiment[i] = (
            0.85 * nlp_sentiment[i - 1]
            + 0.3 * log_returns[i] / daily_vol
            + 0.15 * rng.standard_normal()
        )

    # --- 构造 DataFrame ---
    dates = pd.bdate_range(start="2020-01-01", periods=n_rows, freq="D")
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
