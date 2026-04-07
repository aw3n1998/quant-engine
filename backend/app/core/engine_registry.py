# backend/app/core/engine_registry.py
"""
引擎注册表
使用注册表模式，新增引擎只需调用 register 方法即可被系统自动发现
"""
from __future__ import annotations

from typing import Type

from app.core.base_engine import BaseEngine


class _EngineRegistry:
    def __init__(self) -> None:
        self._store: dict[str, Type[BaseEngine]] = {}

    def register(self, engine_id: str, cls: Type[BaseEngine]) -> None:
        if engine_id in self._store:
            raise ValueError(f"Engine '{engine_id}' already registered")
        self._store[engine_id] = cls

    def get(self, engine_id: str) -> Type[BaseEngine]:
        if engine_id not in self._store:
            raise KeyError(f"Engine '{engine_id}' not found")
        return self._store[engine_id]

    def items(self):
        return self._store.items()

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __getitem__(self, key: str) -> Type[BaseEngine]:
        return self._store[key]

    def __len__(self) -> int:
        return len(self._store)


ENGINE_REGISTRY = _EngineRegistry()
