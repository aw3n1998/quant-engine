# backend/app/utils/mev_fetcher.py
"""
Flashbots MEV 数据拉取器

数据来源：Flashbots Boost Relay 公开 API（无需 API Key）
  https://boost-relay.flashbots.net/relay/v1/data/bidtraces/proposer_payload_delivered

原理：
    以太坊 Merge 后每个区块由 MEV-Boost relay 中继，
    relay 记录每个区块的 MEV 提取价值（block_value，单位 Wei）。
    高 block_value 意味着链上套利/清算/三明治攻击活跃，通常伴随价格剧烈波动。

数据限制：
    - Flashbots relay 约保存最近 30~60 天历史
    - 超出范围的 K 线对应 MEV 分数填 0（触发策略降级逻辑）
    - block_value 仅对 ETH 直接相关；BTC/SOL 等使用 ETH MEV 作为跨资产波动率代理

使用方法：
    mev_series = await fetch_mev_score(df.index, symbol, timeframe)
    df["onchain_mev_score"] = mev_series
"""
from __future__ import annotations

import asyncio
import logging

import pandas as pd

logger = logging.getLogger("quant_engine.mev")

# 以太坊 Merge 时刻的 Unix 时间戳（2022-09-15 06:42:42 UTC）
_MERGE_TIMESTAMP = 1_663_224_162
# 每个 Slot 12 秒
_SECONDS_PER_SLOT = 12

# Flashbots 公开 relay API（无需认证）
_RELAY_URL = "https://boost-relay.flashbots.net/relay/v1/data/bidtraces/proposer_payload_delivered"

# 每次请求最大条数（relay 限制）
_PAGE_SIZE = 100

# pandas resample 别名映射
_TF_TO_PANDAS = {
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}


def _slot_to_timestamp(slot: int) -> pd.Timestamp:
    """将以太坊 slot 编号转换为 UTC 时间戳"""
    unix_ts = _MERGE_TIMESTAMP + slot * _SECONDS_PER_SLOT
    return pd.Timestamp(unix_ts, unit="s", tz="UTC")


def _timestamp_to_slot(ts: pd.Timestamp) -> int:
    """将时间戳转换为近似 slot 编号（Merge 前返回 0）"""
    unix_ts = ts.timestamp()
    delta = unix_ts - _MERGE_TIMESTAMP
    return max(0, int(delta / _SECONDS_PER_SLOT))


async def fetch_mev_score(
    df_index: pd.DatetimeIndex,
    symbol: str,
    timeframe: str,
    max_pages: int = 80,
) -> pd.Series:
    """
    拉取 Flashbots MEV 数据并对齐到 OHLCV 时间戳。

    参数:
        df_index:  OHLCV DataFrame 的时间索引（UTC DatetimeIndex）
        symbol:    交易对（如 "ETH/USDT"），用于日志
        timeframe: K 线时间框架（决定 resample 粒度）
        max_pages: 最多拉取页数（每页 100 个区块 ≈ 20 分钟数据）

    返回:
        pd.Series，索引与 df_index 对齐，值为归一化 MEV 分数（Z-score，≈[-3, 3]）
        无数据的 bar 填 0.0（策略将触发 ATR 降级逻辑）
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx 未安装，MEV 拉取跳过: pip install httpx")
        return pd.Series(0.0, index=df_index)

    # 计算目标时间范围对应的 slot 区间
    end_slot = _timestamp_to_slot(df_index[-1])
    start_slot = _timestamp_to_slot(df_index[0])

    logger.info(
        f"[MEV] 拉取 Flashbots 数据 | slot {start_slot}~{end_slot} | "
        f"约 {(end_slot - start_slot) * 12 / 3600:.1f} 小时"
    )

    all_payloads: list[dict] = []
    cursor = end_slot

    async with httpx.AsyncClient(timeout=20.0) as client:
        for page in range(max_pages):
            try:
                resp = await client.get(
                    _RELAY_URL,
                    params={"limit": _PAGE_SIZE, "cursor": cursor},
                )
                resp.raise_for_status()
                batch: list[dict] = resp.json()
            except Exception as e:
                logger.warning(f"[MEV] 第 {page+1} 页请求失败: {e}")
                break

            if not batch:
                break

            all_payloads.extend(batch)

            # 找到本批次最早的 slot
            oldest_slot = min(int(p["slot"]) for p in batch)
            if oldest_slot <= start_slot:
                break  # 已覆盖目标范围

            cursor = oldest_slot - 1
            await asyncio.sleep(0.25)  # 礼貌限速

    if not all_payloads:
        logger.warning(f"[MEV] 未获取到 Flashbots 数据（{symbol}），MEV 分数填 0")
        return pd.Series(0.0, index=df_index)

    # 解析为时间序列
    rows = []
    for p in all_payloads:
        try:
            slot = int(p["slot"])
            # value 单位为 Wei，转换为 ETH
            value_eth = int(p.get("value", "0")) / 1e18
            ts = _slot_to_timestamp(slot)
            rows.append({"timestamp": ts, "mev_value": value_eth})
        except (KeyError, ValueError):
            continue

    if not rows:
        return pd.Series(0.0, index=df_index)

    mev_raw = (
        pd.DataFrame(rows)
        .set_index("timestamp")
        .sort_index()
        ["mev_value"]
    )

    # 按目标时间框架聚合（求和：该周期内所有区块的 MEV 总量）
    pandas_tf = _TF_TO_PANDAS.get(timeframe, "1h")
    mev_resampled = mev_raw.resample(pandas_tf).sum()

    # Z-score 归一化（保留量级信息，约 ±3 范围）
    mean = mev_resampled.mean()
    std = mev_resampled.std() + 1e-10
    mev_normalized = (mev_resampled - mean) / std

    # 对齐到 OHLCV 索引
    # 先 forward-fill 填充 relay 未覆盖区间（如历史数据），然后 reindex
    combined_idx = mev_normalized.index.union(df_index)
    mev_ffilled = mev_normalized.reindex(combined_idx).ffill()
    mev_aligned = mev_ffilled.reindex(df_index).fillna(0.0)

    covered = int((mev_aligned != 0.0).sum())
    logger.info(
        f"[MEV] 完成：{len(all_payloads)} 个区块 → {covered}/{len(df_index)} 根K线有MEV数据"
    )

    return mev_aligned
