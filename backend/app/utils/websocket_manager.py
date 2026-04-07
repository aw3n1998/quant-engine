# backend/app/utils/websocket_manager.py
"""
WebSocket 连接管理器
负责维护活跃连接池，广播消息至所有已连接客户端
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    """管理 WebSocket 连接的生命周期与消息广播"""

    def __init__(self) -> None:
        self._active: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._active.append(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._active:
                self._active.remove(ws)

    async def broadcast(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, default=str)
        async with self._lock:
            stale: list[WebSocket] = []
            for ws in self._active:
                try:
                    await ws.send_text(payload)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                self._active.remove(ws)

    async def send_progress(
        self, engine: str, strategy: str, progress: float, message: str
    ) -> None:
        await self.broadcast(
            {
                "type": "progress",
                "engine": engine,
                "strategy": strategy,
                "progress": round(progress, 4),
                "message": message,
            }
        )

    async def send_log(self, level: str, message: str) -> None:
        await self.broadcast({"type": "log", "level": level, "message": message})

    async def send_result(self, data: dict[str, Any]) -> None:
        await self.broadcast({"type": "result", "data": data})


manager = WebSocketManager()
