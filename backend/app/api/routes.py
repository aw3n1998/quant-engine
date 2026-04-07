# backend/app/api/routes.py
"""
REST API 路由
提供策略列表、引擎列表、运行计算、上传数据等接口
"""
from __future__ import annotations

import asyncio
import io
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

from app.config.config import config
from app.core.strategy_registry import STRATEGY_REGISTRY
from app.core.engine_registry import ENGINE_REGISTRY
from app.utils.data_generator import generate_synthetic_data
from app.utils.websocket_manager import manager

router = APIRouter(prefix="/api")

# ---- 内存数据缓存 ----
_data_store: dict[str, pd.DataFrame] = {}


def _get_or_create_data(rows: int | None = None) -> pd.DataFrame:
    key = "default"
    if key not in _data_store:
        n = rows or config.default_data_rows
        _data_store[key] = generate_synthetic_data(n, seed=config.default_seed)
    return _data_store[key]


# ---- Request / Response Models ----

class RunEngineRequest(BaseModel):
    engine: str
    strategies: list[str]
    quick_mode: bool = False
    data_rows: int = 1000
    oos_split: float = 20.0
    target_roi: float = 10.0
    max_drawdown: float = -15.0
    friction_penalty: float = 0.0005
    ppo_timesteps: int = 50000
    optuna_trials: int = 100
    wfv_folds: int = 5


class EngineResult(BaseModel):
    engine: str
    strategy: str
    best_params: dict[str, Any]
    sharpe: float
    calmar: float
    max_drawdown: float
    annual_return: float
    equity_curve: list[float]


# ---- Endpoints ----

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
        result.append({
            "id": eid,
            "name": instance.name,
            "description": instance.description,
        })
    return result


@router.get("/config")
async def get_config() -> dict[str, Any]:
    return config.model_dump()


@router.post("/upload-data")
async def upload_data(file: UploadFile = File(...)) -> dict[str, str]:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported")
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content), parse_dates=True, index_col=0)
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing columns: {missing}")
    _data_store["default"] = df
    return {"status": "ok", "rows": str(len(df))}


@router.post("/run")
async def run_engine(req: RunEngineRequest) -> dict[str, str]:
    if req.engine not in ENGINE_REGISTRY:
        raise HTTPException(400, f"Unknown engine: {req.engine}")
    for sid in req.strategies:
        if sid not in STRATEGY_REGISTRY:
            raise HTTPException(400, f"Unknown strategy: {sid}")

    try:
        config.quick_mode = req.quick_mode
        df = _get_or_create_data(req.data_rows)

        params = {
            "target_roi": req.target_roi,
            "max_drawdown": req.max_drawdown,
            "friction_penalty": req.friction_penalty,
            "ppo_timesteps": req.ppo_timesteps,
            "optuna_trials": req.optuna_trials,
            "wfv_folds": req.wfv_folds,
        }

        asyncio.create_task(_run_in_background(req.engine, req.strategies, df, params))
        return {"status": "started", "engine": req.engine}
    except Exception as e:
        import traceback
        with open('crash.log', 'w') as f:
            f.write(traceback.format_exc())
        raise


async def _run_in_background(
    engine_id: str, strategy_ids: list[str], df: pd.DataFrame, params: dict
) -> None:
    engine_cls = ENGINE_REGISTRY[engine_id]
    engine = engine_cls()

    loop = asyncio.get_running_loop()
    def log_cb(level: str, msg: str) -> None:
        asyncio.run_coroutine_threadsafe(manager.send_log(level, msg), loop)

    if engine_id == 'drl':
        strategies = [STRATEGY_REGISTRY[sid] for sid in strategy_ids]
        try:
            await manager.send_log("info", f"[{engine.name}] Running PPO Fusion on {len(strategies)} strategies")
            result = await asyncio.to_thread(engine.run, strategies, df, log_callback=log_cb, **params)
            result_dict = {
                "engine": engine_id,
                "strategy": "portfolio",
                "strategy_name": "DRL Fusion Portfolio",
                "best_params": result.best_params,
                "sharpe": result.sharpe,
                "calmar": result.calmar,
                "max_drawdown": result.max_drawdown,
                "annual_return": result.annual_return,
                "equity_curve": result.equity_curve,
            }
            await manager.send_result(result_dict)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            await manager.send_log("error", f"[{engine.name}] DRL Fusion failed: {exc}")
    else:
        for sid in strategy_ids:
            strategy = STRATEGY_REGISTRY[sid]
            await manager.send_log("info", f"[{engine.name}] Running strategy: {strategy.name}")
            try:
                result = await asyncio.to_thread(engine.run, strategy, df, log_callback=log_cb, **params)
                result_dict = {
                    "engine": engine_id,
                    "strategy": sid,
                    "strategy_name": strategy.name,
                    "best_params": result.best_params,
                    "sharpe": result.sharpe,
                    "calmar": result.calmar,
                    "max_drawdown": result.max_drawdown,
                    "annual_return": result.annual_return,
                    "equity_curve": result.equity_curve,
                }
                await manager.send_result(result_dict)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                await manager.send_log("error", f"[{engine.name}] {strategy.name} failed: {exc}")


    await manager.send_log("info", f"[{engine.name}] All strategies completed.")
