# backend/app/api/routes.py
"""
REST API 路由
提供策略列表、引擎列表、运行计算、上传数据、Binance 拉取、历史记录等接口
"""
from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config.config import config
from app.core.engine_registry import ENGINE_REGISTRY
from app.core.strategy_registry import STRATEGY_REGISTRY
from app.utils.data_generator import generate_synthetic_data
from app.utils.websocket_manager import manager

logger = logging.getLogger("quant_engine.routes")

router = APIRouter(prefix="/api")

# -----------------------------------------------------------------------
# 内存数据缓存（asyncio.Lock 保证线程安全）
# -----------------------------------------------------------------------
_data_store: dict[str, Any] = {}
_data_lock = asyncio.Lock()


async def _get_or_create_data(rows: int | None = None, timeframe: str = "1d") -> pd.DataFrame:
    async with _data_lock:
        if "current" not in _data_store:
            n = rows or config.default_data_rows
            _data_store["current"] = generate_synthetic_data(n, seed=config.default_seed)
            _data_store["source"] = "synthetic"
            _data_store["timeframe"] = timeframe
        return _data_store["current"]


async def _get_data_source() -> str:
    async with _data_lock:
        return _data_store.get("source", "synthetic")


# -----------------------------------------------------------------------
# Request / Response Models
# -----------------------------------------------------------------------

class RunEngineRequest(BaseModel):
    engine: str
    strategies: list[str]
    quick_mode: bool = False
    data_rows: int = 2000
    oos_split: float = 20.0
    timeframe: str = "1d"          # 新增：时间框架（影响年化因子和WFV窗口）
    target_roi: float = 10.0
    max_drawdown: float = -15.0
    friction_penalty: float = 0.0005
    ppo_timesteps: int = 50000
    optuna_trials: int = 80
    wfv_folds: int = 5
    ga_population: int = 40        # GA 种群大小
    ga_generations: int = 25       # GA 迭代代数


class BinanceFetchRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"           # 日内交易推荐：5m/15m/30m/1h/4h
    limit: int = 3000               # 拉取数量（分页拉取突破1000根上限）
    use_mev: bool = False           # 是否拉取 Flashbots MEV 数据（仅 ETH/USDT 直接相关）
    use_nlp: bool = False           # 是否拉取 WorldNewsAPI 新闻情绪数据
    worldnews_api_key: str = ""     # WorldNewsAPI 密钥（use_nlp=True 时必填）


# -----------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------

@router.get("/strategies")
async def list_strategies() -> list[dict[str, str]]:
    return [
        {"id": sid, "name": s.name, "description": s.description}
        for sid, s in STRATEGY_REGISTRY.items()
    ]


@router.get("/engines")
async def list_engines() -> list[dict[str, str]]:
    result = []
    for eid, engine_cls in ENGINE_REGISTRY.items():
        instance = engine_cls()
        result.append({"id": eid, "name": instance.name, "description": instance.description})
    return result


@router.get("/config")
async def get_config() -> dict[str, Any]:
    return config.model_dump()


@router.post("/upload-data")
async def upload_data(file: UploadFile = File(...)) -> dict[str, str]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "仅支持 CSV 文件")

    # 文件大小限制（50MB）
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "文件超过 50MB 限制")

    try:
        df = pd.read_csv(io.BytesIO(content), parse_dates=True, index_col=0)
    except Exception as e:
        raise HTTPException(400, f"CSV 解析失败: {e}")

    # 必须列检查
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"缺少必需列: {sorted(missing)}")

    # 可选列：缺失时填0（相关策略自动降级）
    optional = ["funding_rate", "ob_imbalance", "onchain_mev_score", "nlp_sentiment"]
    for col in optional:
        if col not in df.columns:
            df[col] = 0.0

    async with _data_lock:
        _data_store["current"] = df
        _data_store["source"] = "csv"
        _data_store["timeframe"] = "1d"  # CSV 默认假设日线

    logger.info(f"CSV 上传成功: {len(df)} 行")
    return {"status": "ok", "rows": str(len(df))}


@router.post("/fetch-binance")
async def fetch_binance(req: BinanceFetchRequest) -> dict[str, Any]:
    """
    从 Binance 拉取历史 OHLCV 数据（分页，支持 >1000 根）
    日内交易推荐: timeframe='1h' limit=3000~5000
    """
    from app.utils.binance_fetcher import SUPPORTED_SYMBOLS, SUPPORTED_TIMEFRAMES, fetch_ohlcv_paginated

    if req.symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(400, f"不支持的交易对: {req.symbol}。支持: {SUPPORTED_SYMBOLS}")
    if req.timeframe not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(400, f"不支持的时间框架: {req.timeframe}。支持: {SUPPORTED_TIMEFRAMES}")
    if not (10 <= req.limit <= 100_000):
        raise HTTPException(400, "limit 范围: 10 ~ 100000")
    if req.use_nlp and not req.worldnews_api_key.strip():
        raise HTTPException(400, "use_nlp=true 时需提供 worldnews_api_key")

    await manager.broadcast({
        "type": "log", "level": "info",
        "message": f"[Binance] 正在拉取 {req.symbol} {req.timeframe} × {req.limit} 根K线...",
    })

    try:
        df = await fetch_ohlcv_paginated(req.symbol, req.timeframe, req.limit)
    except Exception as e:
        logger.exception("Binance OHLCV 拉取失败")
        raise HTTPException(502, f"Binance 拉取失败: {e}")

    # ── 并发拉取 MEV 和 NLP 数据（可选）──────────────────────────────────
    mev_task = nlp_task = None

    if req.use_mev:
        from app.utils.mev_fetcher import fetch_mev_score
        await manager.broadcast({
            "type": "log", "level": "info",
            "message": "[MEV] 正在拉取 Flashbots 链上 MEV 数据...",
        })
        mev_task = asyncio.create_task(
            fetch_mev_score(df.index, req.symbol, req.timeframe)
        )

    if req.use_nlp:
        from app.utils.nlp_fetcher import fetch_nlp_sentiment
        await manager.broadcast({
            "type": "log", "level": "info",
            "message": f"[NLP] 正在拉取 WorldNewsAPI 新闻情绪数据（{req.symbol}）...",
        })
        nlp_task = asyncio.create_task(
            fetch_nlp_sentiment(df.index, req.symbol, req.timeframe, req.worldnews_api_key)
        )

    # 等待附加数据拉取完成
    if mev_task is not None:
        try:
            mev_series = await mev_task
            df["onchain_mev_score"] = mev_series.values
            covered = int((mev_series != 0).sum())
            await manager.broadcast({
                "type": "log", "level": "info",
                "message": f"[MEV] 完成：{covered}/{len(df)} 根K线有真实 MEV 数据",
            })
        except Exception as e:
            logger.warning(f"MEV 拉取失败（非致命）: {e}")
            await manager.broadcast({
                "type": "log", "level": "warning",
                "message": f"[MEV] 拉取失败，使用降级逻辑: {e}",
            })

    if nlp_task is not None:
        try:
            nlp_series = await nlp_task
            df["nlp_sentiment"] = nlp_series.values
            covered = int((nlp_series != 0).sum())
            await manager.broadcast({
                "type": "log", "level": "info",
                "message": f"[NLP] 完成：{covered}/{len(df)} 根K线有新闻情绪数据",
            })
        except Exception as e:
            logger.warning(f"NLP 拉取失败（非致命）: {e}")
            await manager.broadcast({
                "type": "log", "level": "warning",
                "message": f"[NLP] 拉取失败，使用降级逻辑: {e}",
            })
    # ─────────────────────────────────────────────────────────────────────

    async with _data_lock:
        _data_store["current"] = df
        source_tag = f"binance:{req.symbol}:{req.timeframe}"
        if req.use_mev:
            source_tag += "+mev"
        if req.use_nlp:
            source_tag += "+nlp"
        _data_store["source"] = source_tag
        _data_store["timeframe"] = req.timeframe

    date_range = f"{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}"
    await manager.broadcast({
        "type": "log", "level": "info",
        "message": f"[Binance] 已加载 {req.symbol} {len(df)} 根{req.timeframe}K线 ({date_range})",
    })

    return {
        "status": "ok",
        "rows": len(df),
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "date_range": date_range,
        "mev_enabled": req.use_mev,
        "nlp_enabled": req.use_nlp,
    }


@router.post("/run")
async def run_engine(req: RunEngineRequest) -> dict[str, str]:
    if req.engine not in ENGINE_REGISTRY:
        raise HTTPException(400, f"未知引擎: {req.engine}")
    for sid in req.strategies:
        if sid not in STRATEGY_REGISTRY:
            raise HTTPException(400, f"未知策略: {sid}")

    try:
        config.quick_mode = req.quick_mode

        async with _data_lock:
            if "current" not in _data_store:
                _data_store["current"] = generate_synthetic_data(
                    req.data_rows, seed=config.default_seed
                )
                _data_store["source"] = "synthetic"
                _data_store["timeframe"] = req.timeframe
            df = _data_store["current"]
            data_source = _data_store.get("source", "synthetic")

        params = {
            "target_roi":      req.target_roi,
            "max_drawdown":    req.max_drawdown,
            "friction_penalty": req.friction_penalty,
            "ppo_timesteps":   req.ppo_timesteps,
            "optuna_trials":   req.optuna_trials,
            "wfv_folds":       req.wfv_folds,
            "oos_split":       req.oos_split,
            "timeframe":       req.timeframe,
            "ga_population":   req.ga_population,
            "ga_generations":  req.ga_generations,
        }

        asyncio.create_task(
            _run_in_background(req.engine, req.strategies, df, params, data_source)
        )
        return {"status": "started", "engine": req.engine}

    except Exception as e:
        logger.exception("启动引擎任务失败")
        raise HTTPException(500, str(e))


# -----------------------------------------------------------------------
# 历史记录端点
# -----------------------------------------------------------------------

@router.get("/history")
async def get_history(limit: int = 50) -> list[dict]:
    from app.utils.persistence import load_history
    return await load_history(limit=limit)


@router.get("/history/{run_id}")
async def get_history_run(run_id: str) -> dict:
    from app.utils.persistence import load_run
    record = await load_run(run_id)
    if record is None:
        raise HTTPException(404, f"记录不存在: {run_id}")
    return record


@router.delete("/history/{run_id}")
async def delete_history_run(run_id: str) -> dict[str, str]:
    from app.utils.persistence import delete_run
    success = await delete_run(run_id)
    if not success:
        raise HTTPException(404, f"记录不存在: {run_id}")
    return {"status": "deleted", "run_id": run_id}


# -----------------------------------------------------------------------
# 后台运行任务
# -----------------------------------------------------------------------

async def _run_in_background(
    engine_id: str,
    strategy_ids: list[str],
    df: pd.DataFrame,
    params: dict,
    data_source: str,
) -> None:
    engine_cls = ENGINE_REGISTRY[engine_id]
    engine = engine_cls()

    loop = asyncio.get_running_loop()

    def log_cb(level: str, msg: str) -> None:
        asyncio.run_coroutine_threadsafe(manager.send_log(level, msg), loop)

    def broadcast_cb(data: dict) -> None:
        asyncio.run_coroutine_threadsafe(manager.broadcast(data), loop)

    # 广播：任务开始
    await manager.broadcast({
        "type": "run_status",
        "status": "running",
        "engine": engine_id,
    })

    try:
        # DRL 和 GA 引擎都接收策略列表（多策略融合）
        if engine_id in ("drl", "genetic"):
            strategies = [STRATEGY_REGISTRY[sid] for sid in strategy_ids]
            await manager.send_log(
                "info",
                f"[{engine.name}] 启动 {engine_id.upper()} 融合引擎 | {len(strategies)} 个策略",
            )
            result = await asyncio.to_thread(
                engine.run, strategies, df,
                log_callback=log_cb,
                broadcast_fn=broadcast_cb,
                **params,
            )
            result_dict = _build_result_dict(engine_id, "portfolio", f"{engine.name} Portfolio", result)
            await manager.send_result(result_dict)
            await _persist(engine_id, strategy_ids, data_source, params["timeframe"], result_dict)

        # 贝叶斯引擎：每策略独立优化，最后汇总因子权重
        else:
            optimized_signals: dict[str, pd.Series] = {}

            for sid in strategy_ids:
                strategy = STRATEGY_REGISTRY[sid]
                await manager.send_log("info", f"[{engine.name}] 优化策略: {strategy.name}")
                try:
                    result = await asyncio.to_thread(
                        engine.run, strategy, df,
                        log_callback=log_cb,
                        **params,
                    )
                    result_dict = _build_result_dict(engine_id, sid, strategy.name, result)
                    await manager.send_result(result_dict)
                    await _persist(engine_id, [sid], data_source, params["timeframe"], result_dict)

                    # 收集最优信号供因子权重元优化
                    oos_split = params.get("oos_split", 20.0) / 100.0
                    split_idx = int(len(df) * (1 - oos_split))
                    df_oos = df.iloc[split_idx:]
                    try:
                        sig = strategy.generate_signals(df_oos, result.best_params)
                        optimized_signals[sid] = sig
                    except Exception:
                        pass

                except Exception as exc:
                    logger.exception(f"策略 {strategy.name} 失败")
                    await manager.send_log("error", f"[{engine.name}] {strategy.name} 失败: {exc}")

            # 多策略因子权重元优化（≥2 个策略时执行）
            if len(optimized_signals) >= 2:
                from app.engines.bayesian_engine import run_factor_weight_optimization
                await manager.send_log("info", f"[{engine.name}] 计算因子权重元优化...")
                factor_weights = await asyncio.to_thread(
                    run_factor_weight_optimization,
                    optimized_signals,
                    params["timeframe"],
                    min(50, params.get("optuna_trials", 50) // 2),
                )
                # 广播因子权重摘要
                await manager.broadcast({
                    "type": "factor_weights",
                    "data": factor_weights,
                })
                await manager.send_log(
                    "info",
                    f"[{engine.name}] 因子权重: " +
                    " | ".join(f"{k}: {v:.3f}" for k, v in factor_weights.items()),
                )

        await manager.send_log("info", f"[{engine.name}] 全部完成。等待指令。")

    except Exception as exc:
        logger.exception("后台任务异常")
        await manager.send_log("error", f"[{engine.name}] 任务失败: {exc}")
        await manager.broadcast({"type": "run_status", "status": "error", "message": str(exc)})
        return

    # 广播：任务完成
    await manager.broadcast({"type": "run_status", "status": "complete"})


def _build_result_dict(
    engine_id: str,
    strategy_id: str,
    strategy_name: str,
    result,
) -> dict[str, Any]:
    return {
        "engine":         engine_id,
        "strategy":       strategy_id,
        "strategy_name":  strategy_name,
        "best_params":    result.best_params,
        "sharpe":         result.sharpe,
        "calmar":         result.calmar,
        "max_drawdown":   result.max_drawdown,
        "annual_return":  result.annual_return,
        "equity_curve":   result.equity_curve,
        "extra_plots":    result.extra_plots or {},
        "weight_history": result.weight_history or [],
        "strategy_names": result.strategy_names or [],
    }


async def _persist(
    engine_id: str,
    strategy_ids: list[str],
    data_source: str,
    timeframe: str,
    result_dict: dict,
) -> None:
    try:
        from app.utils.persistence import save_result
        await save_result(engine_id, strategy_ids, data_source, timeframe, result_dict)
    except Exception as e:
        logger.warning(f"持久化失败（非致命）: {e}")
