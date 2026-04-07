# backend/app/main.py
"""
FastAPI 应用入口
挂载 REST 路由与 WebSocket 端点，配置 CORS 中间件
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.api.websocket import router as ws_router

# 触发策略和引擎的自动注册
import app.strategies  # noqa: F401
import app.engines  # noqa: F401

app = FastAPI(
    title="Crypto Quant Terminal",
    description="Multi-engine extensible quantitative trading terminal",
    version="1.0.0",
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
