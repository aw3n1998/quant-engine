import gymnasium as gym
from gymnasium import spaces
import numpy as np


class CryptoPortfolioEnv(gym.Env):
    """
    加密货币投资组合管理的自定义 Gymnasium 环境

    ┌─────────────────────────────────────────────────────────────────┐
    │               三重防过拟合机制设计意图（架构级注释）                    │
    │                                                                 │
    │  1. 单利累积（非复利）：                                           │
    │     portfolio_value 每步线性加减 step_return，而非复利的乘积。        │
    │     复利会指数放大早期偶然收益，让 PPO 学会"押注幸运序列"的策略。       │
    │     单利迫使智能体追求稳定的正期望，而非短期暴利后持仓。              │
    │                                                                 │
    │  2. 调仓摩擦惩罚（Friction Penalty）：                             │
    │     每步 reward -= L1(target_weights, prev_weights) × penalty。   │
    │     模拟真实的手续费与滑点，惩罚无意义的频繁换仓。                    │
    │     PPO 因此学会"不动则已，动则精准"，专注于真正的市场信号。           │
    │                                                                 │
    │  3. 高斯白噪声注入观测（Gaussian Noise）：                          │
    │     观测向量上叠加 σ=noise_std 的正态随机扰动。                     │
    │     防止 PPO 记忆特定历史 K 线的精确价格序列（过拟合到单条路径）。      │
    │     等效于数据增强，让智能体学习对噪声鲁棒的投资逻辑，而非背历史数据。  │
    └─────────────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        target_returns: np.ndarray,
        target_roi: float = 10.0,
        max_drawdown: float = -15.0,
        friction_penalty: float = 0.0005,
        noise_std: float = 0.002,
    ):
        super().__init__()

        # 确保形态为 2D: (Time, N_assets)
        if len(target_returns.shape) == 1:
            self.returns = target_returns.reshape(-1, 1)
        else:
            self.returns = target_returns

        # 动态 n_assets：由传入数据的列数决定，不硬编码12
        self.n_assets = self.returns.shape[1]
        self.n_steps = self.returns.shape[0]

        self.target_roi = target_roi / 100.0      # 如 10.0 → 0.10
        self.max_drawdown_limit = max_drawdown / 100.0  # 如 -15.0 → -0.15
        self.friction_penalty = friction_penalty
        self.noise_std = noise_std

        # 动作空间：n_assets 维原始动作，step 中做 Softmax 归一化
        self.action_space = spaces.Box(
            low=-10, high=10, shape=(self.n_assets,), dtype=np.float32
        )

        # 观测空间：[3步收益窗口 × n_assets] + [净值] + [当前权重 × n_assets]
        self.window = 3
        obs_dim = self.window * self.n_assets + 1 + self.n_assets
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )

        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._current_step = self.window
        self._portfolio_value = 1.0
        self._peak_value = 1.0
        self._weights = np.ones(self.n_assets, dtype=np.float32) / self.n_assets
        # 权重时序历史（用于 OOS 看板的堆积面积图）
        self.weight_history: list[list[float]] = []
        return self._get_obs(), {}

    def _get_obs(self) -> np.ndarray:
        start = self._current_step - self.window
        recent_ret = self.returns[start: self._current_step].flatten()

        # 【高斯噪声注入】：防止 PPO 死记特定历史价格序列
        noise = self.np_random.normal(0, self.noise_std, size=recent_ret.shape)
        noisy_ret = recent_ret + noise

        obs = np.concatenate(
            [noisy_ret, [self._portfolio_value], self._weights],
            dtype=np.float32,
        )
        return obs

    def step(self, action: np.ndarray):
        # Softmax 归一化，将原始动作映射为仓位权重（和为 1）
        exp_a = np.exp(action - np.max(action))
        target_weights = (exp_a / exp_a.sum()).astype(np.float32)

        raw_return = self.returns[self._current_step]
        # 在真实收益上叠加噪声（训练时），评估时 noise_std=0
        noise = self.np_random.normal(0, self.noise_std, size=raw_return.shape)
        noisy_return = raw_return + noise

        # ----------------------------------------------------------------
        # 【Reward 计算：单利 + 摩擦 + 风险惩罚】
        #
        # step_return = Σ(weight_i × return_i) - friction - risk_penalty
        #
        # friction_cost：惩罚调仓行为，鼓励持仓稳定性
        # risk_penalty：当某资产当日出现大幅负收益时给予额外惩罚，
        #               防止 PPO 配置高风险资产追逐极端收益
        # ----------------------------------------------------------------
        friction_cost = (
            np.sum(np.abs(target_weights - self._weights)) * self.friction_penalty
        )
        # 风险惩罚：最差资产负收益的 10% 作为额外扣减
        worst_loss = max(0.0, -float(np.min(noisy_return)))
        risk_penalty = worst_loss * 0.1

        step_return = float(np.dot(target_weights, noisy_return)) - friction_cost - risk_penalty

        # 单利累积净值
        self._portfolio_value += step_return
        self._peak_value = max(self._peak_value, self._portfolio_value)
        current_dd = (self._portfolio_value - self._peak_value) / max(self._peak_value, 1e-8)

        self._weights = target_weights

        # 记录权重时序（评估阶段使用，用于堆积面积图）
        self.weight_history.append(target_weights.tolist())

        reward = step_return

        terminated = False

        # 跌破最大回撤上限：毁灭级惩罚并终止
        if current_dd <= self.max_drawdown_limit:
            reward -= 1.0
            terminated = True
        # 提前达成目标 ROI：强正向奖励并终止
        elif self._portfolio_value - 1.0 >= self.target_roi:
            reward += 1.0
            terminated = True

        self._current_step += 1
        if self._current_step >= self.n_steps - 1:
            terminated = True

        return (
            self._get_obs(),
            reward,
            terminated,
            False,
            {"step_pnl": step_return, "weights": target_weights.tolist()},
        )
