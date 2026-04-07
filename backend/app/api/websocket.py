# backend/app/api/websocket.py
"""
WebSocket 端点
客户端通过此端点建立长连接，接收服务端推送的进度、日志和结果
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.utils.websocket_manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        while True:
            # 保持连接存活，接收客户端心跳或指令
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)
