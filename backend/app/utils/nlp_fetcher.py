# backend/app/utils/nlp_fetcher.py
"""
WorldNewsAPI 新闻情绪拉取器

数据来源：WorldNewsAPI (https://worldnewsapi.com)
    需要 API Key（免费层每天 1000 次请求）
    申请地址：https://worldnewsapi.com/register

API 说明：
    GET https://api.worldnewsapi.com/search-news
    Headers: x-api-key: <YOUR_KEY>
    参数:
        text                  关键词（如 "Bitcoin BTC"）
        language              语言（en）
        earliest-publish-date 开始时间（"2024-01-01 00:00:00"）
        latest-publish-date   结束时间
        number                每页条数（最大 100）
        offset                分页偏移
        sort                  排序字段（publish-time）
        sort-direction        排序方向（ASC / DESC）
    返回:
        {news: [{title, text, publish_date, sentiment, ...}], total_results, ...}
        sentiment 字段：[-1, 1]，负数为利空，正数为利多

使用方法：
    nlp_series = await fetch_nlp_sentiment(df.index, "BTC/USDT", "1h", api_key="xxx")
    df["nlp_sentiment"] = nlp_series
"""
from __future__ import annotations

import asyncio
import logging

import pandas as pd

logger = logging.getLogger("quant_engine.nlp")

_WORLDNEWS_URL = "https://api.worldnewsapi.com/search-news"
_PAGE_SIZE = 100

# 交易对 → 搜索关键词（精准匹配主流币种新闻）
_SYMBOL_KEYWORDS: dict[str, str] = {
    "BTC/USDT":  "Bitcoin BTC",
    "ETH/USDT":  "Ethereum ETH",
    "SOL/USDT":  "Solana SOL",
    "BNB/USDT":  "BNB Binance",
    "XRP/USDT":  "XRP Ripple",
    "DOGE/USDT": "Dogecoin DOGE",
    "ADA/USDT":  "Cardano ADA",
    "AVAX/USDT": "Avalanche AVAX",
    "DOT/USDT":  "Polkadot DOT",
    "MATIC/USDT":"Polygon MATIC",
}

# pandas resample 别名映射
_TF_TO_PANDAS = {
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}


async def fetch_nlp_sentiment(
    df_index: pd.DatetimeIndex,
    symbol: str,
    timeframe: str,
    api_key: str,
    max_pages: int = 20,
) -> pd.Series:
    """
    拉取 WorldNewsAPI 新闻并提取情绪分数，对齐到 OHLCV 时间戳。

    参数:
        df_index:  OHLCV DataFrame 的时间索引（UTC DatetimeIndex）
        symbol:    交易对（如 "BTC/USDT"）
        timeframe: K 线时间框架（决定情绪聚合粒度）
        api_key:   WorldNewsAPI 密钥
        max_pages: 最多拉取页数（每页 100 条新闻）

    返回:
        pd.Series，索引与 df_index 对齐，值为聚合情绪分数（[-1, 1]）
        无新闻覆盖的 bar 填 0.0（策略使用成交量异常降级逻辑）
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx 未安装，NLP 拉取跳过: pip install httpx")
        return pd.Series(0.0, index=df_index)

    if not api_key or api_key.strip() == "":
        logger.warning("[NLP] 未提供 WorldNewsAPI Key，跳过情绪拉取")
        return pd.Series(0.0, index=df_index)

    keywords = _SYMBOL_KEYWORDS.get(symbol, symbol.split("/")[0])

    # 格式化时间范围（WorldNewsAPI 要求 "YYYY-MM-DD HH:MM:SS" 格式）
    earliest = df_index[0].strftime("%Y-%m-%d %H:%M:%S")
    latest   = df_index[-1].strftime("%Y-%m-%d %H:%M:%S")

    logger.info(f"[NLP] 拉取 WorldNewsAPI | 关键词: {keywords} | {earliest} ~ {latest}")

    all_articles: list[dict] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for page in range(max_pages):
            offset = page * _PAGE_SIZE
            try:
                resp = await client.get(
                    _WORLDNEWS_URL,
                    params={
                        "text":                  keywords,
                        "language":              "en",
                        "earliest-publish-date": earliest,
                        "latest-publish-date":   latest,
                        "number":                _PAGE_SIZE,
                        "offset":                offset,
                        "sort":                  "publish-time",
                        "sort-direction":        "ASC",
                    },
                    headers={"x-api-key": api_key},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"[NLP] 第 {page+1} 页请求失败: {e}")
                break

            articles = data.get("news", [])
            if not articles:
                break

            all_articles.extend(articles)

            # 如果本页不足一页，说明已取完
            if len(articles) < _PAGE_SIZE:
                break

            await asyncio.sleep(0.5)  # 礼貌限速（免费层 ~1 req/s）

    if not all_articles:
        logger.warning(f"[NLP] 未获取到新闻数据（{symbol}），情绪分数填 0")
        return pd.Series(0.0, index=df_index)

    # 解析为时间序列
    rows = []
    for article in all_articles:
        pub_date = article.get("publish_date")
        sentiment = article.get("sentiment")
        if pub_date is None or sentiment is None:
            continue
        try:
            ts = pd.to_datetime(pub_date, utc=True)
            rows.append({"timestamp": ts, "sentiment": float(sentiment)})
        except (ValueError, TypeError):
            continue

    if not rows:
        return pd.Series(0.0, index=df_index)

    sent_raw = (
        pd.DataFrame(rows)
        .set_index("timestamp")
        .sort_index()
        ["sentiment"]
    )

    # 按目标时间框架聚合（均值：该时段内所有新闻的平均情绪）
    pandas_tf = _TF_TO_PANDAS.get(timeframe, "1h")
    sent_resampled = sent_raw.resample(pandas_tf).mean()

    # 前向填充（保持情绪状态直到下一条新闻更新）
    combined_idx = sent_resampled.index.union(df_index)
    sent_ffilled = sent_resampled.reindex(combined_idx).ffill()
    sent_aligned = sent_ffilled.reindex(df_index).fillna(0.0)

    covered = int((sent_aligned != 0.0).sum())
    logger.info(
        f"[NLP] 完成：{len(all_articles)} 条新闻 → {covered}/{len(df_index)} 根K线有情绪数据"
    )

    return sent_aligned
