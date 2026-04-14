# backend/app/utils/persistence.py
"""
SQLite 异步持久化层
使用 aiosqlite 存储所有引擎运行历史，支持跨会话结果回放
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

import aiosqlite

# 数据库路径（相对于 backend/ 的工作目录）
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "quant_engine.db")
DB_PATH = os.path.normpath(DB_PATH)


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS run_history (
    run_id         TEXT PRIMARY KEY,
    timestamp      TEXT NOT NULL,
    engine         TEXT NOT NULL,
    strategies     TEXT NOT NULL,        -- JSON array of strategy ids
    data_source    TEXT NOT NULL,        -- 'synthetic' | 'csv' | 'binance:BTC/USDT:1h'
    timeframe      TEXT NOT NULL DEFAULT '1d',
    sharpe         REAL,
    calmar         REAL,
    max_drawdown   REAL,
    annual_return  REAL,
    equity_curve   TEXT,                 -- JSON float array
    best_params    TEXT,                 -- JSON object
    weight_history TEXT,                 -- JSON (DRL/GA weight matrix)
    extra_plots    TEXT,                 -- JSON (metadata only, no full chart objects)
    batch_id       TEXT                  -- Optional batch ID for grouped runs
)
"""


async def init_db() -> None:
    """在应用启动时初始化数据库，创建表（幂等）"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        try:
            await db.execute("ALTER TABLE run_history ADD COLUMN batch_id TEXT")
        except Exception:
            pass
        await db.commit()


async def save_result(
    engine_id: str,
    strategy_ids: list[str],
    data_source: str,
    timeframe: str,
    result_dict: dict[str, Any],
    batch_id: str | None = None,
) -> str:
    """持久化一次引擎运行结果，返回 run_id"""
    run_id = str(uuid.uuid4())
    ts = datetime.utcnow().isoformat()

    # extra_plots 可能含大型 Plotly 图对象，只存轻量元数据
    extra_meta = {}
    if result_dict.get("extra_plots"):
        ep = result_dict["extra_plots"]
        if "factor_weights" in ep:
            extra_meta["factor_weights"] = ep["factor_weights"]
        if "convergence" in ep:
            extra_meta["convergence_len"] = len(ep.get("convergence", []))

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO run_history
              (run_id, timestamp, engine, strategies, data_source, timeframe,
               sharpe, calmar, max_drawdown, annual_return,
               equity_curve, best_params, weight_history, extra_plots, batch_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                ts,
                engine_id,
                json.dumps(strategy_ids, ensure_ascii=False),
                data_source,
                timeframe,
                result_dict.get("sharpe"),
                result_dict.get("calmar"),
                result_dict.get("max_drawdown"),
                result_dict.get("annual_return"),
                json.dumps(result_dict.get("equity_curve", []), ensure_ascii=False),
                json.dumps(result_dict.get("best_params", {}), ensure_ascii=False, default=str),
                json.dumps(result_dict.get("weight_history", []), ensure_ascii=False),
                json.dumps(extra_meta, ensure_ascii=False),
                batch_id,
            ),
        )
        await db.commit()

    return run_id


async def load_history(limit: int = 50) -> list[dict]:
    """返回最近 N 条历史（不含完整 equity_curve，用于列表展示）"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT run_id, timestamp, engine, strategies, data_source, timeframe,
                   sharpe, calmar, max_drawdown, annual_return, batch_id
            FROM run_history
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()

    result = []
    for row in rows:
        d = dict(row)
        d["strategies"] = json.loads(d["strategies"])
        result.append(d)
    return result


async def load_run(run_id: str) -> dict | None:
    """返回单条完整历史记录（含 equity_curve）"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM run_history WHERE run_id = ?", (run_id,)
        )
        row = await cursor.fetchone()

    if row is None:
        return None

    d = dict(row)
    for key in ("strategies", "equity_curve", "best_params", "weight_history", "extra_plots"):
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                pass
    return d


async def delete_run(run_id: str) -> bool:
    """删除指定运行记录，返回是否成功"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM run_history WHERE run_id = ?", (run_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
