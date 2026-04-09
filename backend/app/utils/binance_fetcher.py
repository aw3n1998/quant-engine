# backend/app/utils/binance_fetcher.py
"""
Binance 历史 OHLCV 数据拉取器

使用 ccxt.async_support 拉取 Binance 现货历史 K 线。
支持分页拉取（突破单次 1000 根上限）。
对于日内交易（1h/4h），自动使用对应时间框架。
"""
from __future__ import annotations

import asyncio
import logging

import pandas as pd

logger = logging.getLogger("quant_engine.binance")

# 支持的交易对和时间框架
SUPPORTED_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "DOT/USDT", "MATIC/USDT",
]

# -----------------------------------------------------------------------
# 【时间框架说明】
# 日内交易应使用 5m/15m/30m/1h/4h，而非 1d（日线）。
# 1d   1000 根 = 约 2.7 年      适合中长期策略
# 4h   1000 根 = 约 166 天      摆动交易
# 1h   1000 根 = 约 41 天       日内（建议 total_limit=3000~5000）
# 30m  1000 根 = 约 20 天       短线
# 15m  1000 根 = 约 10 天       短线
# 5m   1000 根 = 约 3.5 天      高频日内（建议 total_limit=10000+）
# -----------------------------------------------------------------------
SUPPORTED_TIMEFRAMES = ["1d", "4h", "1h", "30m", "15m", "5m"]

# 每次 API 请求最大 K 线数（Binance 限制）
BINANCE_MAX_PER_REQUEST = 1000


async def fetch_ohlcv_paginated(
    symbol: str,
    timeframe: str,
    total_limit: int = 1000,
) -> pd.DataFrame:
    """
    分页拉取 Binance OHLCV 数据。
    Binance 每次最多返回 1000 根，本函数自动循环拉取直到满足 total_limit。

    参数:
        symbol:      交易对，如 "BTC/USDT"
        timeframe:   时间框架，如 "1h"、"4h"、"1d"
        total_limit: 目标 K 线总数（建议日内: 1h→3000, 4h→1500, 1d→1000）

    返回:
        pd.DataFrame with columns: open, high, low, close, volume, funding_rate,
                                   ob_imbalance, onchain_mev_score, nlp_sentiment
    """
    try:
        import ccxt.async_support as ccxt
    except ImportError:
        raise RuntimeError("ccxt 未安装，请运行: pip install ccxt")

    # 从环境变量中读取代理配置
    import os
    proxy_url = os.getenv("all_proxy") or os.getenv("https_proxy") or os.getenv("http_proxy")

    config = {
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    }

    if proxy_url:
        # 对于 ccxt.async_support，应使用 'proxy' 键而非 'proxies' 字典
        # 且国内环境建议使用 http 协议前缀（Clash/V2Ray等通常在同一端口支持 http/socks5）
        if "socks5" in proxy_url:
            proxy_url = proxy_url.replace("socks5://", "http://")
        
        config["proxy"] = proxy_url
        logger.info(f"正在通过代理拉取币安数据 (ccxt async): {proxy_url}")
    else:
        logger.warning("未检测到代理环境变量 (all_proxy/https_proxy)，国内访问可能失败")

    exchange = ccxt.binance(config)


    all_ohlcv: list = []

    try:
        # 向前分批拉取：从最早时间开始，向后累积
        since: int | None = None

        # 先拉一批以确定最早时间戳
        first_batch = await exchange.fetch_ohlcv(
            symbol, timeframe, limit=min(BINANCE_MAX_PER_REQUEST, total_limit)
        )
        if not first_batch:
            raise RuntimeError(f"Binance 返回空数据: {symbol} {timeframe}")

        all_ohlcv = first_batch

        # 如果需要更多，继续向前拉取
        while len(all_ohlcv) < total_limit:
            oldest_ts = all_ohlcv[0][0]
            # 推算一个间隔（毫秒）以确定向前的 since
            if len(all_ohlcv) >= 2:
                interval_ms = all_ohlcv[1][0] - all_ohlcv[0][0]
            else:
                interval_ms = _timeframe_to_ms(timeframe)

            batch_limit = min(BINANCE_MAX_PER_REQUEST, total_limit - len(all_ohlcv))
            since_ts = oldest_ts - interval_ms * batch_limit

            batch = await exchange.fetch_ohlcv(
                symbol, timeframe, since=since_ts, limit=batch_limit
            )
            if not batch:
                break

            # 只保留时间戳早于当前最早的
            new_bars = [b for b in batch if b[0] < oldest_ts]
            if not new_bars:
                break

            all_ohlcv = new_bars + all_ohlcv
            await asyncio.sleep(0.3)  # 遵守 Binance 限速

    finally:
        await exchange.close()

    # 截取最新的 total_limit 根
    all_ohlcv = all_ohlcv[-total_limit:]

    df = pd.DataFrame(
        all_ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)

    # 确保数值类型
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.dropna(subset=["close"], inplace=True)

    # -----------------------------------------------------------------------
    # 【可选字段填充】
    # ob_imbalance、onchain_mev_score、nlp_sentiment 无法从 Binance 公共 API 获取，
    # 填充为 0.0。依赖这些字段的策略将自动触发降级逻辑。
    # funding_rate 仅对永续合约有意义，日内现货交易设为 0。
    # -----------------------------------------------------------------------
    df["funding_rate"] = 0.0
    df["ob_imbalance"] = 0.0
    df["onchain_mev_score"] = 0.0
    df["nlp_sentiment"] = 0.0

    logger.info(
        f"Binance 数据拉取完成: {symbol} {timeframe} | "
        f"{len(df)} 根 | {df.index[0]} ~ {df.index[-1]}"
    )
    return df


def _timeframe_to_ms(timeframe: str) -> int:
    """将时间框架字符串转换为毫秒数"""
    mapping = {
        "1m":  60_000,
        "5m":  300_000,
        "15m": 900_000,
        "30m": 1_800_000,
        "1h":  3_600_000,
        "4h":  14_400_000,
        "1d":  86_400_000,
    }
    return mapping.get(timeframe, 3_600_000)


def get_recommended_limit(timeframe: str) -> int:
    """
    根据时间框架返回推荐的 K 线数量。
    目标：覆盖约 6 个月的历史数据。
    """
    recommendations = {
        "1d":  180,    # 半年日线
        "4h":  1080,   # 半年4h线（180天 × 6）
        "1h":  4320,   # 半年1h线（180天 × 24）
        "30m": 8640,   # 半年30m线
        "15m": 17280,  # 半年15m线
        "5m":  51840,  # 半年5m线（180天 × 288）
    }
    return recommendations.get(timeframe, 1000)
