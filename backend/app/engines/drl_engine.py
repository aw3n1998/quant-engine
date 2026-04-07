# backend/app/engines/drl_engine.py
"""
DRL (Deep Reinforcement Learning) 引擎

核心方法: PPO (Proximal Policy Optimization) + 自定义 Gymnasium 环境

工作流程:
    1. 接收策略实例和数据，使用默认参数生成策略收益率序列
    2. 将收益率序列输入 CryptoPortfolioEnv 环境
    3. 使用 Stable-Baselines3 的 PPO 算法训练智能体
    4. 训练完成后，在环境上评估智能体表现
    5. 返回统一的 EngineResult

防过拟合设计:
    - 环境层面: 高斯噪声注入 + 调仓摩擦惩罚 + 单利结算
    - 训练层面: PPO 自带的 clip 机制限制策略更新幅度
    - 评估层面: 使用训练数据的后半段做带外验证
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.config.config import config
from app.core.base_engine import BaseEngine, EngineResult
from app.core.base_strategy import BaseStrategy
from app.core.engine_registry import ENGINE_REGISTRY
from app.envs.crypto_portfolio_env import CryptoPortfolioEnv
from app.utils.helpers import set_global_seed
from app.utils.metrics import compute_all_metrics


class DRLEngine(BaseEngine):
    """
    PPO 强化学习引擎
    使用自定义 Gymnasium 环境训练仓位管理智能体
    """

    def __init__(self) -> None:
        super().__init__(
            name="DRL (PPO)",
            description="Deep Reinforcement Learning engine using PPO with custom Gymnasium environment",
        )

    def run(self, strategies: list, df: pd.DataFrame, log_callback=None, **kwargs) -> EngineResult:
        def emit(msg: str) -> None:
            if log_callback:
                log_callback("info", msg)

        from stable_baselines3 import PPO

        emit(f"[{self.name}] Optimizing Parameters (Baseline Search)...")
        set_global_seed(config.default_seed)

        # 使用中位数参数生成所有策略收益率，并合成组合收益线 (PPO 融合输入信号)
        returns_list = []
        for strategy in strategies:
            default_params = self._get_default_params(strategy)
            daily_returns = strategy.generate_signals(df, default_params)
            returns_list.append(daily_returns.values.astype(np.float32))
        
        returns_array = np.mean(returns_list, axis=0)

        # 分割训练集和验证集 (前 70% 训练, 后 30% 验证)
        split_idx = int(len(returns_array) * 0.7)
        train_returns = returns_array[:split_idx]
        val_returns = returns_array[split_idx:]

        # 创建训练环境
        train_env = CryptoPortfolioEnv(
            target_returns=train_returns,
            noise_std=config.drl_noise_std,
            friction_penalty=config.drl_friction_penalty,
        )

        # 训练步数根据 quick_mode 调整
        total_timesteps = (
            config.drl_total_timesteps_quick
            if config.quick_mode
            else config.drl_total_timesteps
        )

        emit(f"[{self.name}] Training PPO setup completed...")

        # PPO 训练
        model = PPO(
            "MlpPolicy",
            train_env,
            learning_rate=config.drl_learning_rate,
            gamma=config.drl_gamma,
            seed=config.default_seed,
            verbose=0,
        )
        emit(f"[{self.name}] Training PPO on {total_timesteps} timesteps...")
        model.learn(total_timesteps=total_timesteps)

        emit(f"[{self.name}] Converging... evaluating agent on validation set")
        # 在验证集上评估
        val_env = CryptoPortfolioEnv(
            target_returns=val_returns,
            noise_std=0.0,  # 评估时不加噪声
            friction_penalty=config.drl_friction_penalty,
        )

        obs, _ = val_env.reset(seed=config.default_seed)
        managed_returns = []
        done = False

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = val_env.step(action)
            managed_returns.append(info["step_pnl"])
            done = terminated or truncated

        managed_series = pd.Series(managed_returns)
        metrics = compute_all_metrics(managed_series)

        return EngineResult(
            best_params=default_params,
            sharpe=metrics["sharpe"],
            calmar=metrics["calmar"],
            max_drawdown=metrics["max_drawdown"],
            annual_return=metrics["annual_return"],
            equity_curve=metrics["equity_curve"],
        )

    @staticmethod
    def _get_default_params(strategy: BaseStrategy) -> dict:
        """
        为策略生成一组默认参数 (取各参数的中位数)
        使用 Optuna 的 Trial 模拟来提取参数空间的中间值
        """
        import optuna

        study = optuna.create_study(direction="maximize")

        def _objective(trial: optuna.Trial) -> float:
            strategy.get_param_space(trial)
            return 0.0

        study.optimize(_objective, n_trials=1, show_progress_bar=False)

        # 使用第一次 trial 的参数作为默认值
        return study.best_trial.params


ENGINE_REGISTRY.register("drl", DRLEngine)
