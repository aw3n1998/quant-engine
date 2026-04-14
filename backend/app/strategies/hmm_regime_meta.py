"""
HMM 市场状态元策略 (Hidden Markov Model Regime Meta Strategy)

核心思想:
    使用隐马尔可夫模型 (HMM) 动态识别市场当前的隐含状态（如牛市、熊市、震荡市）。
    根据识别出的状态，动态切换底层交易逻辑：
    - 状态0 (低波动震荡) -> 均值回归 (RSI超买超卖)
    - 状态1 (高波动趋势) -> 趋势跟随 (EMA突破)
    - 状态2 (极端恐慌/单边) -> 停止交易或防守模式
    
量化逻辑:
    为了防止未来函数，HMM 模型必须滚动拟合 (Rolling Fit) 或只使用截止到当前 t 时刻的数据。
    但 HMM 拟合较慢，本策略采用简化的滚动窗口拟合（每 N 根 K 线更新一次模型），
    并使用 predict 进行实时状态推断。
"""
from __future__ import annotations

import warnings

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY
from app.utils.friction import apply_friction_costs

# 抑制 hmmlearn 可能的收敛警告
warnings.filterwarnings("ignore", module="hmmlearn")

try:
    from hmmlearn import hmm
except ImportError:
    hmm = None


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


class HMMRegimeMetaStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="HMM Regime Meta",
            description="3-State Hidden Markov Model to dynamically switch between trend and mean-reversion logic",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "hmm_window":      trial.suggest_int("hmm_window", 200, 500),
            "ema_fast":        trial.suggest_int("ema_fast", 5, 20),
            "ema_slow":        trial.suggest_int("ema_slow", 30, 80),
            "rsi_period":      trial.suggest_int("rsi_period", 7, 21),
            "retrain_freq":    trial.suggest_int("retrain_freq", 10, 50),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        if hmm is None:
            # 如果缺少依赖，返回空仓
            return pd.Series(0.0, index=df.index)

        hmm_window = params["hmm_window"]
        ema_f_p = params["ema_fast"]
        ema_s_p = params["ema_slow"]
        rsi_p = params["rsi_period"]
        retrain_freq = params["retrain_freq"]

        close = df["close"]
        returns = close.pct_change().fillna(0)
        
        # 预计算底层指标
        ema_fast = close.ewm(span=ema_f_p, adjust=False).mean()
        ema_slow = close.ewm(span=ema_s_p, adjust=False).mean()
        trend_dir = (ema_fast > ema_slow).astype(float) * 2 - 1  # 1 or -1
        rsi = _rsi(close, rsi_p)

        # 准备 HMM 特征：收益率和滚动波动率
        volatility = returns.rolling(14).std().fillna(0)
        features = pd.concat([returns, volatility], axis=1).values

        position = pd.Series(0.0, index=df.index)
        
        model = None
        state_mapping = {}  # 映射 0,1,2 到 'trend', 'range', 'panic'
        
        pos = 0.0
        # 从能收集到足够特征的位置开始
        for i in range(hmm_window, len(df)):
            # 定期重训练 HMM 模型以适应市场环境变化
            if i % retrain_freq == 0 or model is None:
                train_X = features[i - hmm_window:i]
                model = hmm.GaussianHMM(n_components=3, covariance_type="diag", n_iter=50, random_state=42)
                try:
                    model.fit(train_X)
                    
                    # 分析各个隐状态的特征来打标签
                    # state 0, 1, 2
                    means_vol = model.means_[:, 1]  # 波动率维度的均值
                    
                    sorted_idx = np.argsort(means_vol)
                    # 假设：波动率最小的为盘整(range)，居中的为趋势(trend)，最大的为恐慌(panic)
                    state_mapping = {
                        sorted_idx[0]: 'range',
                        sorted_idx[1]: 'trend',
                        sorted_idx[2]: 'panic'
                    }
                except Exception:
                    model = None
            
            # 如果模型训练失败，保持上一个状态或空仓
            if model is None:
                position.iloc[i] = 0.0
                continue
                
            # 推断当前属于哪个状态（仅使用到当前的特征）
            curr_X = features[i-1:i+1] # 使用最近两步
            try:
                curr_state = model.predict(curr_X)[-1]
                regime = state_mapping.get(curr_state, 'range')
            except Exception:
                regime = 'range'
                
            # 状态元路由逻辑
            c = close.iloc[i]
            r = rsi.iloc[i]
            td = trend_dir.iloc[i]
            
            if regime == 'trend':
                # 趋势市：完全跟随均线金死叉方向
                pos = td
            elif regime == 'range':
                # 盘整市：高抛低吸，RSI 策略
                if r < 30:
                    pos = 1.0
                elif r > 70:
                    pos = -1.0
                else:
                    pos = 0.0 # 盘整中轨休息
            elif regime == 'panic':
                # 极端恐慌：空仓避险或轻仓跟随
                pos = 0.0
                
            position.iloc[i] = pos

        return apply_friction_costs(position, df)


STRATEGY_REGISTRY.register("hmm_regime_meta", HMMRegimeMetaStrategy())
