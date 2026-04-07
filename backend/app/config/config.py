# backend/app/config/config.py
"""
全局配置模块
集中管理所有可调参数，便于统一修改和环境切换
"""
from pydantic import BaseModel


class AppConfig(BaseModel):
    """应用全局配置"""

    # --- 数据 ---
    default_data_rows: int = 2000
    default_seed: int = 42

    # --- DRL 引擎 ---
    drl_total_timesteps: int = 50_000
    drl_total_timesteps_quick: int = 5_000
    drl_learning_rate: float = 3e-4
    drl_gamma: float = 0.99
    drl_friction_penalty: float = 0.001
    drl_noise_std: float = 0.002

    # --- Bayesian 引擎 ---
    bayesian_n_trials: int = 80
    bayesian_n_trials_quick: int = 10
    bayesian_n_splits: int = 5
    bayesian_n_splits_quick: int = 3
    bayesian_min_train_size: int = 252

    # --- WebSocket ---
    ws_heartbeat_interval: int = 30

    # --- Quick Mode ---
    quick_mode: bool = False


config = AppConfig()
