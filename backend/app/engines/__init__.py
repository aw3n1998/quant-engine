# backend/app/engines/__init__.py
"""
引擎包初始化
导入所有引擎模块以触发自动注册
"""
from app.engines import drl_engine  # noqa: F401
from app.engines import bayesian_engine  # noqa: F401
