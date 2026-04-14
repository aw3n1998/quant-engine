# backend/app/main.py
"""
FastAPI 应用入口
挂载 REST 路由与 WebSocket 端点，配置 CORS 中间件，初始化数据库
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 配置结构化日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("quant_engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库，关闭时清理资源"""
    from app.utils.persistence import init_db
    logger.info("初始化 SQLite 数据库...")
    await init_db()
    logger.info("Quant Engine 就绪")
    yield
    logger.info("Quant Engine 关闭")


from app.api.routes import router as api_router
from app.api.websocket import router as ws_router

# 触发策略和引擎的自动注册
import app.strategies  # noqa: F401
import app.engines     # noqa: F401

tags_metadata = [
    {"name": "System", "description": "Health checks and system status"},
    {"name": "Market Data", "description": "Operations with CSV upload and Binance OHLCV fetching"},
    {"name": "Trading Engine", "description": "Launch optimization engines, fetch strategies and config"},
    {"name": "History & Validation", "description": "Manage OOS validation, history logs, and engine fusion"},
]

app = FastAPI(
    title="Crypto Quant Terminal",
    description="Multi-engine extensible quantitative trading terminal with advanced backtesting capabilities.",
    version="2.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
