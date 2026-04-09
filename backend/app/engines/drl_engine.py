# backend/app/engines/drl_engine.py
"""
DRL (Deep Reinforcement Learning) 引擎

核心方法: PPO (Proximal Policy Optimization) + 自定义 Gymnasium 环境

工作流程:
    1. 接收多个策略实例，生成各策略收益率矩阵（二维，不平均）
    2. 将 (T, N_strategies) 矩阵传入 CryptoPortfolioEnv
    3. PPO 学习如何动态分配 N 个策略的权重（而非单一资产）
    4. 使用扩展窗口 WFV 训练 + OOS 评估（与 Bayesian/GA 保持一致）
    5. 返回统一的 EngineResult（含 weight_history 供堆积面积图）

防过拟合设计:
    - 环境层面: 高斯噪声注入 + 调仓摩擦惩罚 + 单利结算 + 风险惩罚
    - 训练层面: PPO clip 机制 + 较高熵系数（鼓励探索）
    - 评估层面: 扩展窗口 WFV（≤3折），OOS 拼接后统一计算指标
    - 热启动: 每折直接复用上折策略权重，加速收敛

WFV 与 Bayesian/GA 的一致性:
    - 均使用扩展窗口（IS 逐折增大，OOS 向后滑动）
    - 均以拼接的 OOS 收益序列计算最终 Sharpe/Calmar
    - DRL 上限 3 折（Bayesian/GA 默认 5 折），原因：PPO 训练成本高
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import numpy as np
import pandas as pd

from app.config.config import config
from app.core.base_engine import BaseEngine, EngineResult
from app.core.base_strategy import BaseStrategy
from app.core.engine_registry import ENGINE_REGISTRY
from app.envs.crypto_portfolio_env import CryptoPortfolioEnv
from app.utils.helpers import set_global_seed
from app.utils.metrics import compute_all_metrics

logger = logging.getLogger("quant_engine.drl")


class DRLEngine(BaseEngine):
    """
    PPO 强化学习引擎（扩展窗口 WFV 版本）
    将多策略信号作为 N 维资产，训练 PPO 学习最优权重分配。
    """

    def __init__(self) -> None:
        super().__init__(
            name="DRL (PPO)",
            description="Deep Reinforcement Learning with PPO + WFV: learns optimal strategy weight allocation",
        )

    def run(
        self,
        strategies: list,
        df: pd.DataFrame,
        log_callback: Callable | None = None,
        broadcast_fn: Callable | None = None,
        **kwargs,
    ) -> EngineResult:
        def emit(msg: str) -> None:
            if log_callback:
                log_callback("info", msg)

        from stable_baselines3 import PPO
        from stable_baselines3.common.callbacks import BaseCallback

        set_global_seed(config.default_seed)

        timeframe   = kwargs.get("timeframe",        config.default_timeframe)
        target_roi  = kwargs.get("target_roi",       10.0)
        max_dd      = kwargs.get("max_drawdown",     -15.0)
        friction    = kwargs.get("friction_penalty", config.drl_friction_penalty)
        total_steps = kwargs.get("ppo_timesteps",    config.drl_total_timesteps)
        oos_split   = kwargs.get("oos_split",        20.0) / 100.0

        if config.quick_mode:
            total_steps = config.drl_total_timesteps_quick

        # ── WFV 参数：DRL 训练成本高，上限 3 折 ──────────────────────────
        # 每折步数 = total_steps / wfv_folds，总训练量与用户设定相同
        wfv_folds     = min(kwargs.get("wfv_folds", 5), 3)
        steps_per_fold = max(total_steps // wfv_folds, 5000)

        total_bars = len(df)
        oos_size   = max(int(total_bars * oos_split), 30)
        fold_size  = max(oos_size // wfv_folds, 15)
        # 最小 IS 大小（fold 0 的 IS 长度）
        min_is_size = total_bars - oos_size

        emit(f"[{self.name}] WFV {wfv_folds} 折 | 每折 {steps_per_fold} PPO步 | "
             f"总数据 {total_bars}bars | OOS {oos_size}bars / {fold_size}bars/折")

        # ── 一次性生成全量信号矩阵 ───────────────────────────────────────
        # DRL 不优化策略参数，故无 look-ahead 风险，全量生成效率更高
        emit(f"[{self.name}] 并行生成 {len(strategies)} 个策略全量信号...")

        def _gen_signal(strategy, full_df, default_params):
            return strategy.generate_signals(full_df, default_params)

        with ThreadPoolExecutor(max_workers=min(len(strategies), 8)) as executor:
            futs = {
                executor.submit(_gen_signal, s, df, self._get_default_params(s)): s
                for s in strategies
            }
            full_returns_list = []
            strategy_names = []
            for future, s in futs.items():
                sig = future.result()
                full_returns_list.append(sig.values.astype(np.float32))
                strategy_names.append(s.name)

        full_matrix = np.column_stack(full_returns_list)   # (T, N_strategies)
        emit(f"[{self.name}] 信号矩阵: {full_matrix.shape}")

        # ── 模型路径（按策略组合哈希，保证不同组合不互相覆盖）──────────
        strategy_hash = hashlib.md5(
            "_".join(sorted(strategy_names)).encode()
        ).hexdigest()[:8]
        model_dir  = os.path.join(os.path.dirname(__file__), "..", "..", "data", "models")
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, f"ppo_{strategy_hash}.zip")

        # ── PPO 超参数（全折统一，以便折间热启动）──────────────────────
        n_steps = min(2048, max(64, min_is_size // 4))

        # SB3 进度回调（仅最后一折广播，避免刷屏）
        class ProgressCB(BaseCallback):
            def __init__(self_, total_ts, bfn):
                super().__init__(verbose=0)
                self_.total_ts  = total_ts
                self_.bfn       = bfn
                self_._last     = 0
                self_._interval = max(total_ts // 40, 256)

            def _on_step(self_) -> bool:
                n = self_.num_timesteps
                if n - self_._last >= self_._interval:
                    self_._last = n
                    mean_r = 0.0
                    if self_.model.ep_info_buffer:
                        mean_r = float(np.mean([i["r"] for i in self_.model.ep_info_buffer]))
                    entropy = 0.0
                    try:
                        entropy = float(self_.model.policy.get_distribution(
                            self_.model.policy.obs_to_tensor(
                                self_.training_env.reset()[0]
                            )[0]
                        ).entropy().mean().item())
                    except Exception:
                        pass
                    if self_.bfn:
                        self_.bfn({
                            "type": "progress_plot",
                            "data": {"step": n, "reward": mean_r, "entropy": entropy},
                        })
                return True

        # ── 扩展窗口 WFV 主循环 ──────────────────────────────────────────
        all_oos_returns: list[float] = []
        weight_history: list[list[float]] = []
        fold_model = None   # 上折模型用于热启动

        for fold_i in range(wfv_folds):
            is_end  = min_is_size + fold_i * fold_size
            oos_end = min(is_end + fold_size, total_bars)
            if is_end >= total_bars:
                break

            is_matrix  = full_matrix[:is_end]
            oos_matrix = full_matrix[is_end:oos_end]

            emit(f"[{self.name}] Fold {fold_i+1}/{wfv_folds}: "
                 f"IS[0:{is_end}] → OOS[{is_end}:{oos_end}]")

            train_env = CryptoPortfolioEnv(
                target_returns=is_matrix,
                target_roi=target_roi,
                max_drawdown=max_dd,
                friction_penalty=friction,
                noise_std=config.drl_noise_std,
            )

            if fold_model is None:
                # Fold 0: 从头初始化（尝试加载历史模型热启动）
                if os.path.exists(model_path):
                    emit(f"[{self.name}] 载入历史模型热启动: ppo_{strategy_hash}.zip")
                    fold_model = PPO.load(model_path, env=train_env)
                else:
                    emit(f"[{self.name}] 初始化 PPO (MLP {list(config.drl_net_arch)}, "
                         f"ent_coef={config.drl_ent_coef})")
                    fold_model = PPO(
                        "MlpPolicy", train_env,
                        policy_kwargs=dict(net_arch=list(config.drl_net_arch)),
                        learning_rate=config.drl_learning_rate,
                        gamma=config.drl_gamma,
                        ent_coef=config.drl_ent_coef,
                        n_steps=n_steps,
                        batch_size=64,
                        seed=config.default_seed,
                        verbose=0,
                    )
            else:
                # 后续折：复用上折策略权重（set_env 更换环境，不重置权重）
                fold_model.set_env(train_env)

            is_last_fold = (fold_i == wfv_folds - 1) or (is_end + fold_size >= total_bars)
            cb = ProgressCB(steps_per_fold, broadcast_fn if is_last_fold else None)
            fold_model.learn(total_timesteps=steps_per_fold, callback=cb, reset_num_timesteps=True)

            # OOS 评估（无噪声，确定性策略）
            val_env = CryptoPortfolioEnv(
                target_returns=oos_matrix,
                target_roi=target_roi,
                max_drawdown=max_dd,
                friction_penalty=friction,
                noise_std=0.0,
            )
            obs, _ = val_env.reset(seed=config.default_seed)
            fold_returns: list[float] = []
            done = False
            while not done:
                action, _ = fold_model.predict(obs, deterministic=True)
                obs, _, terminated, truncated, info = val_env.step(action)
                fold_returns.append(info["step_pnl"])
                done = terminated or truncated

            calmar_fold = (sum(fold_returns) / max(abs(min(fold_returns, default=0)), 1e-9)
                           if fold_returns else 0.0)
            emit(f"[{self.name}] Fold {fold_i+1} OOS Calmar≈{calmar_fold:.3f}, "
                 f"Returns={len(fold_returns)}步")

            all_oos_returns.extend(fold_returns)
            weight_history = val_env.weight_history   # 最后一折的权重时序

        # ── 保存最终模型（最后一折 = 最多训练数据）──────────────────────
        if fold_model is not None:
            fold_model.save(model_path)
            emit(f"[{self.name}] 模型已保存: ppo_{strategy_hash}.zip")

        # ── 以拼接 OOS 序列计算最终指标（与 Bayesian/GA 指标计算完全一致）─
        managed_series = pd.Series(all_oos_returns, dtype=np.float32)
        metrics = compute_all_metrics(managed_series, timeframe=timeframe)
        emit(f"[{self.name}] WFV OOS 汇总: Calmar={metrics['calmar']:.3f}, "
             f"Sharpe={metrics['sharpe']:.3f}, MDD={metrics['max_drawdown']:.2%}")

        return EngineResult(
            best_params={"wfv_folds": wfv_folds, "steps_per_fold": steps_per_fold,
                         "strategy_names": strategy_names},
            sharpe=metrics["sharpe"],
            calmar=metrics["calmar"],
            max_drawdown=metrics["max_drawdown"],
            annual_return=metrics["annual_return"],
            equity_curve=metrics["equity_curve"],
            weight_history=weight_history,
            strategy_names=strategy_names,
        )

    @staticmethod
    def _get_default_params(strategy: BaseStrategy) -> dict:
        """为策略提取参数空间的中位数默认值（MockTrial 模式）"""
        import optuna

        study = optuna.create_study(direction="maximize")

        def _obj(trial: optuna.Trial) -> float:
            strategy.get_param_space(trial)
            return 0.0

        study.optimize(_obj, n_trials=1, show_progress_bar=False)
        return study.best_trial.params


ENGINE_REGISTRY.register("drl", DRLEngine)
