import gymnasium as gym
from gymnasium import spaces
import numpy as np

class CryptoPortfolioEnv(gym.Env):
    def __init__(self, target_returns: np.ndarray, target_roi=10.0, max_drawdown=-15.0, friction_penalty=0.0005, noise_std=0.002):
        super(CryptoPortfolioEnv, self).__init__()
        
        # 确保形态为 2D: (Time, N_assets)
        if len(target_returns.shape) == 1:
            self.returns = target_returns.reshape(-1, 1)
        else:
            self.returns = target_returns
            
        self.n_assets = self.returns.shape[1]
        self.n_steps = self.returns.shape[0]
        
        self.target_roi = target_roi / 100.0  # 比如 10.0 变为 0.10
        self.max_drawdown = max_drawdown / 100.0 # 比如 -15.0 变为 -0.15
        self.friction_penalty = friction_penalty
        self.noise_std = noise_std
        
        # ------------------------------------------------------------------
        # 【多维权重动作】
        # 输出 12 维等长的原始动作，在 step 中做 Softmax 处理得到资金分配权重
        # ------------------------------------------------------------------
        self.action_space = spaces.Box(low=-10, high=10, shape=(self.n_assets,), dtype=np.float32)
        
        self.window = 3 # 使用最近 3 个步长的信号作为观测特征
        obs_dim = self.window * self.n_assets + 1 + self.n_assets
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32)
        
        self.reset()
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._current_step = self.window
        self._portfolio_value = 1.0
        self._peak_value = 1.0
        self._weights = np.ones(self.n_assets) / self.n_assets
        return self._get_obs(), {}
        
    def _get_obs(self):
        start = self._current_step - self.window
        recent_ret = self.returns[start:self._current_step].flatten()
        # 加入高斯噪声特征状态
        noise = self.np_random.normal(0, self.noise_std, size=recent_ret.shape)
        noisy_ret = recent_ret + noise
        
        obs = np.concatenate([
            noisy_ret,
            [self._portfolio_value],
            self._weights
        ], dtype=np.float32)
        return obs
        
    def step(self, action):
        # 对输出实施 Softmax 归一化
        exp_a = np.exp(action - np.max(action))
        target_weights = exp_a / np.sum(exp_a)
        
        raw_return = self.returns[self._current_step]
        noise = self.np_random.normal(0, self.noise_std, size=raw_return.shape)
        noisy_return = raw_return + noise
        
        # ------------------------------------------------------------------
        # 【防过拟合核心机制：“单利 + 摩擦 + 高斯噪声”】
        #
        # 1. 高斯白噪声 (Gaussian Noise): 
        #    通过在真实的 raw_return 上叠加正态分布的随机噪声，破坏了智能体
        #    记忆特定 K 线排列和精确收益率的可能，迫使其学习大趋势特征。
        # 
        # 2. 摩擦惩罚 (Friction Penalty):
        #    计算目标仓位与当前权重的 L1 距离 (绝对差值) 并乘上摩擦系数。
        # 
        # 3. 单利结算 (Simple Interest):
        #    在此 env 中 portfolio_value 呈现 step_return 的线性加法。
        # ------------------------------------------------------------------
        friction_cost = np.sum(np.abs(target_weights - self._weights)) * self.friction_penalty
        
        step_return = float(np.sum(target_weights * noisy_return) - friction_cost)
        
        # 单利累计
        self._portfolio_value += step_return
        
        self._peak_value = max(self._peak_value, self._portfolio_value)
        current_dd = (self._portfolio_value - self._peak_value) / self._peak_value
        
        self._weights = target_weights
        
        reward = step_return
        
        terminated = False
        # 风险惩罚极限：跌破最大回撤，毁灭级惩罚并停止
        if current_dd <= self.max_drawdown:
            reward -= 1.0 
            terminated = True
        # 提前达成目标：强正向奖励并终止
        elif self._portfolio_value - 1.0 >= self.target_roi:
            reward += 1.0 
            terminated = True
            
        self._current_step += 1
        if self._current_step >= self.n_steps - 1:
            terminated = True
            
        return self._get_obs(), reward, terminated, False, {"step_pnl": step_return}
