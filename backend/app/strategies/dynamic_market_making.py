# backend/app/strategies/dynamic_market_making.py
"""
Dynamic Market Making 策略

核心思想:
    做市策略通过在买卖两侧挂单赚取价差 (spread)。
    本策略动态调整 spread 宽度和库存偏移:
    - 波动率高时扩大 spread 以补偿风险
    - 库存偏向一侧时调整报价以吸引反向成交，减少库存风险
    - 模拟思路: 将做市收益近似为 spread/2 减去逆向选择成本

量化逻辑:
    1. 计算已实现波动率 (滚动 close 回报的标准差)
    2. 动态 spread = base_spread + vol_mult * realized_vol
    3. 模拟库存: 根据 ob_imbalance 判断净成交方向
    4. 库存偏移惩罚: inventory_penalty * abs(inventory)
    5. 做市收益 = spread / 2 - 逆向选择损失 - 库存惩罚
    6. 在趋势剧烈 (高动量) 时暂停做市，避免被趋势碾压
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


class DynamicMarketMakingStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="Dynamic Market Making",
            description="Adaptive spread market making with inventory control and trend pause mechanism",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "base_spread": trial.suggest_float("base_spread", 0.001, 0.01),
            "vol_mult": trial.suggest_float("vol_mult", 1.0, 5.0),
            "vol_window": trial.suggest_int("vol_window", 10, 40),
            "inventory_penalty": trial.suggest_float("inventory_penalty", 0.0005, 0.005),
            "momentum_pause": trial.suggest_float("momentum_pause", 0.02, 0.08),
            "mom_period": trial.suggest_int("mom_period", 5, 20),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        base_spread = params["base_spread"]
        vol_mult = params["vol_mult"]
        vol_window = params["vol_window"]
        inv_penalty = params["inventory_penalty"]
        mom_pause = params["momentum_pause"]
        mom_period = params["mom_period"]

        returns = df["close"].pct_change()
        realized_vol = returns.rolling(vol_window).std()
        momentum = returns.rolling(mom_period).mean().abs()

        ob = df["ob_imbalance"]

        strategy_return = pd.Series(0.0, index=df.index)
        inventory = 0.0

        for i in range(vol_window, len(df)):
            vol = realized_vol.iloc[i]
            mom = momentum.iloc[i]

            if np.isnan(vol) or np.isnan(mom):
                continue

            # 趋势过强时暂停做市
            if mom > mom_pause:
                strategy_return.iloc[i] = 0.0
                continue

            dynamic_spread = base_spread + vol_mult * vol

            # 根据订单簿不平衡模拟净成交
            flow = ob.iloc[i] if not np.isnan(ob.iloc[i]) else 0.0
            inventory += flow * 0.1

            # 做市收益 = 半个 spread 减去库存惩罚
            mm_pnl = dynamic_spread / 2.0 - inv_penalty * abs(inventory)

            # 逆向选择成本: 价格变动与库存方向一致时获益，反向时亏损
            price_move = returns.iloc[i] if not np.isnan(returns.iloc[i]) else 0.0
            adverse = -abs(price_move) * 0.3

            strategy_return.iloc[i] = mm_pnl + adverse

            # 库存均值回归
            inventory *= 0.95

        return pd.Series(strategy_return, index=df.index)


STRATEGY_REGISTRY.register("dynamic_market_making", DynamicMarketMakingStrategy())
