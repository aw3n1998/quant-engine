# backend/app/strategies/ml_feature_strategy.py
"""
ML Feature Engineering Strategy（机器学习特征工程策略）

核心思想:
    用 RandomForest 在滚动窗口内训练，自动发现有效特征组合。
    每隔 retrain_freq 根K线重新训练，适应市场变化。
    严格避免未来数据泄漏（只用历史数据训练）。

    特征集（11个）:
    - 价格动量：1/3/5/10根K线收益率
    - 技术指标：RSI、布林带宽度、成交量比率
    - 蜡烛图结构：实体比、上影线比、下影线比
    - 统计：滚动标准差、滚动偏度

    无 sklearn 时降级为 EMA 交叉策略。
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.core.base_strategy import BaseStrategy
from app.core.strategy_registry import STRATEGY_REGISTRY


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """构建11个工程特征（无未来泄漏）"""
    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    open_  = df["open"]
    volume = df["volume"]

    ret = close.pct_change()

    # 价格动量
    r1  = ret
    r3  = close.pct_change(3)
    r5  = close.pct_change(5)
    r10 = close.pct_change(10)

    # RSI
    rsi = _rsi(close, 14)

    # 布林带宽度
    ma20     = close.rolling(20).mean()
    std20    = close.rolling(20).std()
    bb_width = (std20 * 2) / ma20.replace(0, np.nan)

    # 成交量比率
    vol_ma   = volume.rolling(20).mean()
    vol_ratio = volume / vol_ma.replace(0, np.nan)

    # 蜡烛图结构
    rng  = (high - low).replace(0, np.nan)
    body = (close - open_).abs() / rng
    upper_wick = (high - pd.concat([close, open_], axis=1).max(axis=1)) / rng
    lower_wick = (pd.concat([close, open_], axis=1).min(axis=1) - low) / rng

    # 统计特征
    roll_std  = ret.rolling(10).std()
    roll_skew = ret.rolling(15).skew()

    feat = pd.DataFrame({
        "r1": r1, "r3": r3, "r5": r5, "r10": r10,
        "rsi": rsi / 100,
        "bb_width": bb_width,
        "vol_ratio": vol_ratio.clip(0, 5),
        "body": body,
        "upper_wick": upper_wick,
        "lower_wick": lower_wick,
        "roll_std": roll_std,
        "roll_skew": roll_skew.clip(-3, 3),
    }, index=df.index)

    return feat


class MlFeatureStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="ML Feature Engineering",
            description="RandomForest with 11 engineered features, rolling retrain to avoid lookahead bias",
        )

    def get_param_space(self, trial: optuna.Trial) -> dict:
        return {
            "train_period":          trial.suggest_int("train_period",          100, 400),
            "n_estimators":          trial.suggest_int("n_estimators",          20, 80),
            "prediction_threshold":  trial.suggest_float("prediction_threshold", 0.52, 0.72),
            "retrain_freq":          trial.suggest_int("retrain_freq",           10, 40),
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        train_p = params["train_period"]
        n_est   = params["n_estimators"]
        thresh  = params["prediction_threshold"]
        freq    = params["retrain_freq"]

        close     = df["close"]
        daily_ret = close.pct_change()
        position  = pd.Series(0.0, index=df.index)

        try:
            from sklearn.ensemble import RandomForestClassifier

            features = _build_features(df)
            # 目标：下一根K线方向
            target = np.sign(daily_ret.shift(-1)).fillna(0)

            model = None
            warmup = train_p + 30

            for i in range(warmup, len(df)):
                # 定期重训
                if model is None or (i - warmup) % freq == 0:
                    X_train = features.iloc[i - train_p: i].values
                    y_train = target.iloc[i - train_p: i].values
                    valid   = ~np.isnan(X_train).any(axis=1)
                    Xv, yv  = X_train[valid], y_train[valid]
                    if len(np.unique(yv)) < 2 or len(Xv) < 20:
                        continue
                    model = RandomForestClassifier(
                        n_estimators=n_est,
                        max_depth=4,
                        random_state=42,
                        n_jobs=1,
                    )
                    model.fit(Xv, yv)

                if model is None:
                    continue

                x_now = features.iloc[i].values
                if np.isnan(x_now).any():
                    continue

                proba = model.predict_proba([x_now])[0]
                classes = model.classes_
                if 1.0 in classes:
                    p_up = proba[list(classes).index(1.0)]
                    if p_up >= thresh:
                        position.iloc[i] = 1.0
                    elif p_up <= (1 - thresh):
                        position.iloc[i] = -1.0

        except ImportError:
            # sklearn 不可用，降级为 EMA 交叉
            ema_fast = close.ewm(span=12, adjust=False).mean()
            ema_slow = close.ewm(span=26, adjust=False).mean()
            for i in range(30, len(df)):
                if ema_fast.iloc[i] > ema_slow.iloc[i]:
                    position.iloc[i] = 1.0
                elif ema_fast.iloc[i] < ema_slow.iloc[i]:
                    position.iloc[i] = -1.0

        return (position.shift(1) * daily_ret).fillna(0.0)


STRATEGY_REGISTRY.register("ml_feature_sr", MlFeatureStrategy())
