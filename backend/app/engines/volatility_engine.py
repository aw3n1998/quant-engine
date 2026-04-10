# backend/app/engines/volatility_engine.py
"""
Volatility Adaptive Engine（波动率自适应引擎）

核心方法: 按市场波动率分档，为每档独立计算最优策略权重

工作流程:
    1. 计算每根K线的滚动波动率（20根K线滚动收益标准差）
    2. 将波动率分为 3 档:
       - 低波动（< vol_low）→ 按 Sharpe 加权（稳定收益策略优先）
       - 中波动（vol_low ~ vol_high）→ 等权重
       - 高波动（> vol_high）→ 按低回撤加权（防御策略优先）
    3. 在 IS 数据上计算各策略在不同波动率档位下的表现
    4. OOS 阶段逐根K线根据当日波动率选择对应档位权重
    5. 记录完整权重时序

优势:
    - 不同市场环境自动切换策略组合
    - 高波动时自动切入防御模式
    - 计算高效，无需离线优化
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.special import softmax

from app.core.base_engine import BaseEngine, EngineResult
from app.core.base_strategy import BaseStrategy
from app.core.engine_registry import ENGINE_REGISTRY
from app.utils.metrics import compute_all_metrics, sharpe_ratio, max_drawdown

logger = logging.getLogger("quant_engine.volatility")


class VolatilityEngine(BaseEngine):
    def __init__(self) -> None:
        super().__init__(
            name="Volatility Adaptive",
            description="Automatically switches strategy weights based on 3 volatility regimes (low/mid/high)",
        )

    def run(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        log_callback=None,
        **kwargs,
    ) -> EngineResult:
        def emit(msg: str, level: str = "info") -> None:
            if log_callback:
                log_callback(level, msg)

        strategies: list[BaseStrategy] = strategy if isinstance(strategy, list) else [strategy]
        timeframe: str  = kwargs.get("timeframe", "1d")
        oos_split: float = kwargs.get("oos_split", 20.0)
        vol_low: float  = kwargs.get("vol_low", 0.015)
        vol_high: float = kwargs.get("vol_high", 0.035)

        n = len(strategies)
        emit(f"[Volatility] 初始化 | {n} 个策略 | vol_low={vol_low} vol_high={vol_high}")

        # 划分 IS / OOS
        split_idx = int(len(df) * (1 - oos_split / 100))
        df_is  = df.iloc[:split_idx].reset_index(drop=True)
        df_oos = df.iloc[split_idx:].reset_index(drop=True)

        if len(df_is) < 60:
            emit("[Volatility] IS 数据不足", "warning")
            return EngineResult()

        # 计算波动率（20根滚动收益标准差）
        def _rolling_vol(df_: pd.DataFrame, window: int = 20) -> pd.Series:
            ret = df_["close"].pct_change()
            return ret.rolling(window).std().fillna(ret.std())

        is_vol  = _rolling_vol(df_is)
        oos_vol = _rolling_vol(df_oos)

        # 生成各策略在 IS/OOS 上的信号
        emit("[Volatility] 生成策略信号...")
        fake_trial = _FakeTrial()
        is_signals: list[pd.Series]  = []
        oos_signals: list[pd.Series] = []
        strategy_names: list[str]    = []

        for s in strategies:
            try:
                params = s.get_param_space(fake_trial)
                is_sig  = s.generate_signals(df_is,  params)
                oos_sig = s.generate_signals(df_oos, params)
            except Exception:
                is_sig  = pd.Series(0.0, index=df_is.index)
                oos_sig = pd.Series(0.0, index=df_oos.index)
            is_signals.append(is_sig)
            oos_signals.append(oos_sig)
            strategy_names.append(s.name)

        # ─── 按波动率档位计算 IS 权重 ───
        def _regime_weights(signals: list[pd.Series], vol: pd.Series, mode: str) -> np.ndarray:
            """计算某波动率档位下的策略权重"""
            scores = np.zeros(len(signals))
            for i, sig in enumerate(signals):
                if mode == "low":
                    # 低波动：按 Sharpe 加权
                    scores[i] = max(sharpe_ratio(sig, timeframe=timeframe), 0)
                elif mode == "high":
                    # 高波动：按低回撤加权（回撤越小得分越高）
                    mdd = max_drawdown(sig)
                    scores[i] = max(1.0 - mdd, 0)
                else:
                    scores[i] = 1.0  # 中波动：等权

            if scores.sum() < 1e-9:
                return np.ones(len(signals)) / len(signals)
            return softmax(scores * 3)

        # 分 IS 数据到三个档位
        mask_lo = is_vol < vol_low
        mask_hi = is_vol > vol_high
        mask_md = ~mask_lo & ~mask_hi

        emit(f"[Volatility] IS 档位分布: 低={mask_lo.sum()} 中={mask_md.sum()} 高={mask_hi.sum()}")

        # 计算三档权重（基于对应档位的 IS 信号）
        def _masked_signals(signals: list[pd.Series], mask: pd.Series) -> list[pd.Series]:
            return [sig[mask].reset_index(drop=True) for sig in signals]

        w_low  = _regime_weights(_masked_signals(is_signals, mask_lo), is_vol[mask_lo], "low")
        w_mid  = _regime_weights(_masked_signals(is_signals, mask_md), is_vol[mask_md], "mid")
        w_high = _regime_weights(_masked_signals(is_signals, mask_hi), is_vol[mask_hi], "high")

        emit(f"[Volatility] 低波动权重: {[round(w, 3) for w in w_low]}")
        emit(f"[Volatility] 中波动权重: {[round(w, 3) for w in w_mid]}")
        emit(f"[Volatility] 高波动权重: {[round(w, 3) for w in w_high]}")

        # ─── OOS 逐根K线评估 ───
        oos_combined = pd.Series(0.0, index=df_oos.index)
        weight_history: list[list[float]] = []

        for t in range(len(df_oos)):
            vol_t = oos_vol.iloc[t]

            if vol_t < vol_low:
                w = w_low
            elif vol_t > vol_high:
                w = w_high
            else:
                w = w_mid

            weight_history.append(w.tolist())

            ret_t = sum(w[i] * oos_signals[i].iloc[t] for i in range(n))
            oos_combined.iloc[t] = ret_t

        metrics = compute_all_metrics(oos_combined, timeframe=timeframe)

        best_params = {
            **{f"w_low_{s.name}":  float(round(w_low[i],  4)) for i, s in enumerate(strategies)},
            **{f"w_high_{s.name}": float(round(w_high[i], 4)) for i, s in enumerate(strategies)},
        }

        emit(f"[Volatility] OOS Sharpe={metrics['sharpe']:.3f} | Calmar={metrics['calmar']:.3f}")

        return EngineResult(
            best_params=best_params,
            sharpe=metrics["sharpe"],
            calmar=metrics["calmar"],
            max_drawdown=metrics["max_drawdown"],
            annual_return=metrics["annual_return"],
            equity_curve=metrics["equity_curve"],
            weight_history=weight_history,
            strategy_names=strategy_names,
        )


class _FakeTrial:
    """模拟 Optuna Trial，返回参数中值"""
    def suggest_int(self, name: str, low: int, high: int, **kw) -> int:
        return (low + high) // 2

    def suggest_float(self, name: str, low: float, high: float, **kw) -> float:
        return (low + high) / 2


ENGINE_REGISTRY.register("volatility", VolatilityEngine)
