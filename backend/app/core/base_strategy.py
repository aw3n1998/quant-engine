# backend/app/core/base_strategy.py
"""
策略抽象基类 (BaseStrategy)

架构设计意图:
    所有量化策略都必须继承此基类并实现两个核心方法：
    1. get_param_space  -- 定义策略的超参数搜索空间，由优化引擎(Bayesian/DRL)调用
    2. generate_signals -- 根据给定参数在历史数据上生成每日收益率序列

    这种设计将「策略逻辑」与「优化引擎」彻底解耦：
    - 策略只关心"给定参数，如何产生信号和收益"
    - 引擎只关心"如何搜索最优参数"
    - 两者通过 get_param_space / generate_signals 的契约进行交互

扩展步骤:
    1. 在 strategies/ 目录下新建一个 Python 文件
    2. 创建一个继承 BaseStrategy 的类
    3. 实现 get_param_space 和 generate_signals 两个方法
    4. 在文件末尾调用 STRATEGY_REGISTRY.register(strategy_id, instance) 完成注册
    5. 在 strategies/__init__.py 中导入该模块以触发注册
    无需修改任何已有代码
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import optuna
import pandas as pd


class BaseStrategy(ABC):
    """所有策略的抽象基类"""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def get_param_space(self, trial: optuna.Trial) -> dict:
        """
        定义超参数搜索空间
        由 Optuna Trial 对象驱动，返回参数字典
        """
        ...

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """
        根据参数在数据上生成每日收益率序列
        返回值: pd.Series，索引与 df 对齐，值为每日策略收益率
        """
        ...
