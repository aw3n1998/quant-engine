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
    default_timeframe: str = "1d"

    # --- DRL 引擎 ---
    drl_total_timesteps: int = 50_000
    drl_total_timesteps_quick: int = 5_000
    drl_learning_rate: float = 3e-4
    drl_gamma: float = 0.99
    drl_ent_coef: float = 0.01       # 熵系数：提高以鼓励更多探索
    drl_friction_penalty: float = 0.001
    drl_noise_std: float = 0.002
    drl_net_arch: list = [64, 64]     # MLP 网络结构

    # --- Bayesian 引擎 ---
    bayesian_n_trials: int = 80
    bayesian_n_trials_quick: int = 10
    bayesian_n_splits: int = 5
    bayesian_n_splits_quick: int = 3
    bayesian_min_train_size: int = 252  # 1d 基准值（其他 timeframe 按比例缩放）

    # --- Genetic Algorithm 引擎 ---
    ga_population_size: int = 40
    ga_generations: int = 25
    ga_population_size_quick: int = 15
    ga_generations_quick: int = 8
    ga_mutation_rate: float = 0.2      # 每个基因的变异概率
    ga_mutation_sigma: float = 0.1     # 高斯变异标准差
    ga_tournament_k: int = 3           # 锦标赛规模
    ga_elite_ratio: float = 0.1        # 精英保留比例
    ga_crossover_alpha: float = 0.5    # BLX-α 交叉参数

    # --- WebSocket ---
    ws_heartbeat_interval: int = 30

    # --- Quick Mode ---
    quick_mode: bool = False


config = AppConfig()
