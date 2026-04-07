# backend/app/core/strategy_registry.py
"""
策略注册表
使用注册表模式，新增策略只需调用 register 方法即可被系统自动发现
"""
from __future__ import annotations

from app.core.base_strategy import BaseStrategy


class _StrategyRegistry:
    def __init__(self) -> None:
        self._store: dict[str, BaseStrategy] = {}

    def register(self, strategy_id: str, instance: BaseStrategy) -> None:
        if strategy_id in self._store:
            raise ValueError(f"Strategy '{strategy_id}' already registered")
        self._store[strategy_id] = instance

    def get(self, strategy_id: str) -> BaseStrategy:
        if strategy_id not in self._store:
            raise KeyError(f"Strategy '{strategy_id}' not found")
        return self._store[strategy_id]

    def items(self):
        return self._store.items()

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __getitem__(self, key: str) -> BaseStrategy:
        return self._store[key]

    def __len__(self) -> int:
        return len(self._store)


STRATEGY_REGISTRY = _StrategyRegistry()
