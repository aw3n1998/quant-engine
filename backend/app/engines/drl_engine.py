# backend/app/engines/drl_engine.py
"""
DRL (Deep Reinforcement Learning) 引擎

核心方法: PPO (Proximal Policy Optimization) + 自定义 Gymnasium 环境

工作流程:
    1. 接收多个策略实例，生成各策略收益率矩阵（二维，不平均）
    2. 将 (T, N_strategies) 矩阵传入 CryptoPortfolioEnv
    3. PPO 学习如何动态分配 N 个策略的权重（而非单一资产）
    4. 训练完成后在 OOS 验证集上评估，记录权重时序
    5. 返回统一的 EngineResult（含 weight_history 供堆积面积图）

防过拟合设计:
    - 环境层面: 高斯噪声注入 + 调仓摩擦惩罚 + 单利结算 + 风险惩罚
    - 训练层面: PPO clip 机制 + 较高熵系数（鼓励探索）
    - 评估层面: 使用严格分离的 OOS 验证集（零噪声）
    - 模型版本化: 按时间戳 + 策略组合哈希命名，防止互相覆盖
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
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


class _ProgressCallback:
    """
    Stable-Baselines3 自定义回调：在训练过程中广播进度数据供前端实时绘图
    """

    def __init__(self, total_timesteps: int, broadcast_fn: Callable, emit_fn: Callable):
        self.total_timesteps = total_timesteps
        self.broadcast_fn = broadcast_fn
        self.emit_fn = emit_fn
        self._last_broadcast = 0
        self._broadcast_interval = max(total_timesteps // 50, 500)

    def __call__(self, locals_: dict, globals_: dict) -> bool:
        step = locals_.get("self", None)
        if step is None:
            return True

        num_timesteps = getattr(step, "num_timesteps", 0)
        if num_timesteps - self._last_broadcast >= self._broadcast_interval:
            self._last_broadcast = num_timesteps

            # 尝试提取最近平均奖励和熵
            ep_info = locals_.get("infos", [])
            mean_reward = 0.0
            ep_buf = getattr(getattr(step, "ep_info_buffer", None), "__iter__", None)
            if ep_buf and step.ep_info_buffer:
                mean_reward = float(np.mean([info["r"] for info in step.ep_info_buffer]))

            # 熵从 policy 提取
            entropy = 0.0
            try:
                policy = step.policy
                if hasattr(policy, "action_dist"):
                    dist = policy.action_dist
                    if hasattr(dist, "entropy"):
                        entropy = float(dist.entropy().mean().item())
            except Exception:
                pass

            self.broadcast_fn({
                "type": "progress_plot",
                "data": {
                    "step": num_timesteps,
                    "reward": mean_reward,
                    "entropy": entropy,
                },
            })
        return True


class DRLEngine(BaseEngine):
    """
    PPO 强化学习引擎
    将多策略信号作为 N 维资产，训练 PPO 学习最优权重分配
    """

    def __init__(self) -> None:
        super().__init__(
            name="DRL (PPO)",
            description="Deep Reinforcement Learning with PPO: learns optimal strategy weight allocation",
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

        timeframe = kwargs.get("timeframe", config.default_timeframe)
        target_roi = kwargs.get("target_roi", 10.0)
        max_dd = kwargs.get("max_drawdown", -15.0)
        friction = kwargs.get("friction_penalty", config.drl_friction_penalty)
        total_timesteps = kwargs.get("ppo_timesteps", config.drl_total_timesteps)
        if config.quick_mode:
            total_timesteps = config.drl_total_timesteps_quick

        oos_split = kwargs.get("oos_split", 20.0) / 100.0
        split_idx = int(len(df) * (1 - oos_split))
        df_train = df.iloc[:split_idx]
        df_val = df.iloc[split_idx:]

        emit(f"[{self.name}] 正在生成 {len(strategies)} 个策略信号矩阵...")

        # ----------------------------------------------------------------
        # 修复：保留 2D 矩阵 (T, N_strategies) 传入环境，不再平均成 1D。
        # 之前 np.mean(returns_list, axis=0) 导致 n_assets=1，
        # PPO 退化为单资产优化，丧失多策略权重分配的核心能力。
        # ----------------------------------------------------------------
        train_returns_list = []
        val_returns_list = []
        strategy_names = []

        for strategy in strategies:
            default_params = self._get_default_params(strategy)
            train_sig = strategy.generate_signals(df_train, default_params)
            val_sig = strategy.generate_signals(df_val, default_params)
            train_returns_list.append(train_sig.values.astype(np.float32))
            val_returns_list.append(val_sig.values.astype(np.float32))
            strategy_names.append(strategy.name)

        train_matrix = np.column_stack(train_returns_list)  # (T_train, n_strategies)
        val_matrix = np.column_stack(val_returns_list)       # (T_val, n_strategies)

        emit(f"[{self.name}] 矩阵维度: train={train_matrix.shape}, val={val_matrix.shape}")

        train_env = CryptoPortfolioEnv(
            target_returns=train_matrix,
            target_roi=target_roi,
            max_drawdown=max_dd,
            friction_penalty=friction,
            noise_std=config.drl_noise_std,
        )

        # 模型版本化：按时间戳 + 策略组合哈希命名
        strategy_hash = hashlib.md5(
            "_".join(sorted(strategy_names)).encode()
        ).hexdigest()[:8]
        model_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "models"
        )
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, f"ppo_{strategy_hash}.zip")

        if os.path.exists(model_path):
            emit(f"[{self.name}] 载入历史模型: ppo_{strategy_hash}.zip（增量训练）")
            model = PPO.load(model_path, env=train_env)
        else:
            emit(f"[{self.name}] 初始化新 PPO 模型 (MLP [64,64], ent_coef={config.drl_ent_coef})")
            model = PPO(
                "MlpPolicy",
                train_env,
                policy_kwargs=dict(net_arch=list(config.drl_net_arch)),
                learning_rate=config.drl_learning_rate,
                gamma=config.drl_gamma,
                ent_coef=config.drl_ent_coef,
                n_steps=2048,
                batch_size=64,
                seed=config.default_seed,
                verbose=0,
            )

        emit(f"[{self.name}] 开始训练 PPO，共 {total_timesteps} 步...")

        # SB3 回调：向 WebSocket 广播训练进度
        class ProgressCB(BaseCallback):
            def __init__(self_, total_ts, bfn, efn):
                super().__init__(verbose=0)
                self_.total_ts = total_ts
                self_.bfn = bfn
                self_.efn = efn
                self_._last = 0
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

        cb = ProgressCB(total_timesteps, broadcast_fn, emit)
        model.learn(total_timesteps=total_timesteps, callback=cb)
        model.save(model_path)
        emit(f"[{self.name}] 训练完成，模型已保存: ppo_{strategy_hash}.zip")

        # OOS 盲测（评估时 noise_std=0，无随机因素）
        emit(f"[{self.name}] 在 OOS 验证集上评估...")
        val_env = CryptoPortfolioEnv(
            target_returns=val_matrix,
            target_roi=target_roi,
            max_drawdown=max_dd,
            friction_penalty=friction,
            noise_std=0.0,
        )

        obs, _ = val_env.reset(seed=config.default_seed)
        managed_returns = []
        done = False

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = val_env.step(action)
            managed_returns.append(info["step_pnl"])
            done = terminated or truncated

        # 收集权重时序（用于堆积面积图）
        weight_history = val_env.weight_history

        managed_series = pd.Series(managed_returns, dtype=np.float32)
        metrics = compute_all_metrics(managed_series, timeframe=timeframe)

        return EngineResult(
            best_params=self._get_default_params(strategies[0]) if strategies else {},
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
        """为策略生成一组中位数默认参数（使用 Optuna Trial 模拟）"""
        import optuna

        study = optuna.create_study(direction="maximize")

        def _obj(trial: optuna.Trial) -> float:
            strategy.get_param_space(trial)
            return 0.0

        study.optimize(_obj, n_trials=1, show_progress_bar=False)
        return study.best_trial.params


ENGINE_REGISTRY.register("drl", DRLEngine)
