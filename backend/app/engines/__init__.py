# backend/app/engines/__init__.py
"""
引擎包初始化
导入所有引擎模块以触发自动注册
"""
from app.engines import drl_engine        # noqa: F401
from app.engines import bayesian_engine   # noqa: F401
from app.engines import genetic_engine    # noqa: F401
from app.engines import bandit_engine     # noqa: F401
from app.engines import volatility_engine # noqa: F401
from app.engines import ensemble_engine   # noqa: F401
from app.engines import montecarlo_engine # noqa: F401
from app.engines import risk_parity_engine # noqa: F401
