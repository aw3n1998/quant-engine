# backend/app/strategies/__init__.py
"""
策略包初始化
导入所有策略模块以触发自动注册
"""
from app.strategies import fibonacci_resonance  # noqa: F401
from app.strategies import mad_trend  # noqa: F401
from app.strategies import funding_arbitrage  # noqa: F401
from app.strategies import po3_institutional  # noqa: F401
from app.strategies import orderflow_imbalance  # noqa: F401
from app.strategies import mev_capture  # noqa: F401
from app.strategies import statistical_pair  # noqa: F401
from app.strategies import nlp_event_driven  # noqa: F401
from app.strategies import dynamic_market_making  # noqa: F401
from app.strategies import liquidation_hunting  # noqa: F401
from app.strategies import liquidity_hedge_mining  # noqa: F401
from app.strategies import macro_capital_flow  # noqa: F401
