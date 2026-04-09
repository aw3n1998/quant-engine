# backend/app/strategies/__init__.py
"""
策略包初始化
导入所有策略模块以触发自动注册
"""
# 保留策略（纯K线 or 有效降级fallback）
from app.strategies import fibonacci_resonance    # noqa: F401
from app.strategies import mad_trend              # noqa: F401
from app.strategies import po3_institutional      # noqa: F401
from app.strategies import orderflow_imbalance    # noqa: F401
from app.strategies import mev_capture            # noqa: F401
from app.strategies import nlp_event_driven       # noqa: F401
from app.strategies import liquidation_hunting    # noqa: F401

# 新增策略（纯K线，高回报潜力）
from app.strategies import donchian_breakout      # noqa: F401
from app.strategies import bollinger_squeeze      # noqa: F401
from app.strategies import ema_trend_filter       # noqa: F401
from app.strategies import rsi_momentum           # noqa: F401
from app.strategies import volume_price_momentum  # noqa: F401
