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

    def calculate_returns(self, position: pd.Series, daily_ret: pd.Series, commission: float = 0.001) -> pd.Series:
        """
        计算包含真实交易摩擦成本（手续费与滑点）的净收益序列
        """
        pos_shifted = position.shift(1).fillna(0.0)
        turnover = position.diff().abs().fillna(0.0)
        gross_returns = pos_shifted * daily_ret
        net_returns = gross_returns - turnover * commission
        return net_returns.fillna(0.0)

    def apply_position_sizing(self, df: pd.DataFrame, position: pd.Series, target_vol: float = 0.15, half_kelly: bool = True) -> pd.Series:
        """
        Phase 5: 动态仓位缩放管理 (Volatility Targeting & Kelly Criterion)
        基于策略输出的原生信号（如 -1, 0, 1），动态计算波动率并应用凯利公式缩放杠杆。
        
        :param df: OHLCV DataFrame 包含价格数据
        :param position: 原始方向信号序列
        :param target_vol: 目标年化波动率（默认15%）
        :param half_kelly: 是否采用保守的“半凯利”策略（默认开启）
        :return: 缩放后的持仓序列
        """
        import numpy as np
        
        returns = df["close"].pct_change().fillna(0)
        
        # 1. 波动率目标化 (Volatility Targeting)
        # 计算 30 周期滚动波动率 (假设以日或更短周期为主，进行简单缩放)
        rolling_vol = returns.rolling(window=30, min_periods=5).std() * np.sqrt(365)
        # 目标除以实际波动率（实际过高时缩小杠杆）
        vol_scalar = target_vol / rolling_vol.replace(0, np.nan)
        # 最大允许 2.0 倍杠杆，防止极端放大
        vol_scalar = vol_scalar.fillna(1.0).clip(upper=2.0)
        
        # 2. 凯利公式 (Kelly Criterion)
        # f = p - (1-p)/b
        # 此处使用简单的固定保守预估（实际可基于真实滚动胜率计算）
        win_rate = 0.55
        payoff_ratio = 1.5
        kelly_f = win_rate - (1 - win_rate) / payoff_ratio
        if half_kelly:
            kelly_f *= 0.5
        kelly_f = max(0.0, min(1.0, kelly_f))
        
        scaled_position = position * kelly_f * vol_scalar
        return scaled_position.fillna(0.0)
