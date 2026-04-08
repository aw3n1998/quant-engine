# backend/app/core/base_engine.py
"""
引擎抽象基类 (BaseEngine) 与统一结果结构 (EngineResult)

架构设计意图:
    所有优化/训练引擎都必须继承 BaseEngine 并实现 run 方法。
    引擎负责：
    1. 接收策略实例和 DataFrame 数据
    2. 通过各自的优化方法（贝叶斯搜索、强化学习、遗传算法等）寻找最优参数
    3. 返回统一的 EngineResult 结构

    EngineResult 是跨引擎对比的基础：
    - 无论使用 DRL、Bayesian 还是 Genetic 引擎，输出格式一致
    - 前端可以直接将多个 EngineResult 放在同一看板对比

扩展步骤:
    1. 在 engines/ 目录下新建一个 Python 文件
    2. 创建一个继承 BaseEngine 的类
    3. 实现 run(strategy, df) -> EngineResult 方法
    4. 在文件末尾调用 ENGINE_REGISTRY.register(engine_id, cls) 完成注册
    5. 在 engines/__init__.py 中导入该模块以触发注册
    无需修改任何已有代码
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from app.core.base_strategy import BaseStrategy


@dataclass
class EngineResult:
    """
    统一的引擎输出结构，用于多引擎绩效对比

    字段说明:
    - best_params:    最优参数组合（策略超参 or 因子权重）
    - sharpe:         年化夏普比率
    - calmar:         Calmar 比率 (年化收益 / 最大回撤)
    - max_drawdown:   最大回撤 (正数表示损失百分比)
    - annual_return:  年化收益率
    - equity_curve:   净值曲线 (列表形式，便于 JSON 序列化)
    - extra_plots:    额外图表数据（贝叶斯收敛图、GA因子权重图等）
    - weight_history: DRL/GA 策略权重时序矩阵 [[w1,w2,...] per step]
    - strategy_names: 用于 weight_history 图例的策略名列表
    """

    best_params: dict[str, Any] = field(default_factory=dict)
    sharpe: float = 0.0
    calmar: float = 0.0
    max_drawdown: float = 0.0
    annual_return: float = 0.0
    equity_curve: list[float] = field(default_factory=list)
    extra_plots: dict[str, Any] = field(default_factory=dict)
    weight_history: list[list[float]] = field(default_factory=list)
    strategy_names: list[str] = field(default_factory=list)


class BaseEngine(ABC):
    """所有优化引擎的抽象基类"""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def run(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        log_callback: Callable[[str, str], None] | None = None,
    ) -> EngineResult:
        """
        执行优化/训练流程
        返回 EngineResult 实例
        """
        ...
