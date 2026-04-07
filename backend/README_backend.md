# Backend - Crypto Quant Terminal

Python FastAPI backend providing REST API and WebSocket communication for the quantitative trading terminal.

## Architecture

```
app/
  main.py              FastAPI entry point
  config/config.py     Global configuration
  core/                Abstract base classes + registries
  strategies/          12 fully implemented strategies
  engines/             DRL (PPO) + Bayesian (Optuna) engines
  envs/                Custom Gymnasium environment
  api/                 REST routes + WebSocket endpoint
  utils/               Data generation, metrics, helpers
```

## Quick Start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

| Method | Path             | Description                    |
|--------|------------------|--------------------------------|
| GET    | /api/strategies  | List all registered strategies |
| GET    | /api/engines     | List all registered engines    |
| GET    | /api/config      | Get current configuration      |
| POST   | /api/run         | Start engine optimization      |
| POST   | /api/upload-data | Upload custom CSV data         |
| WS     | /ws              | WebSocket for real-time events |

## Adding a New Strategy

1. Create a new file in `app/strategies/`
2. Inherit from `BaseStrategy`
3. Implement `get_param_space()` and `generate_signals()`
4. Register with `STRATEGY_REGISTRY.register("id", Instance())`
5. Import in `app/strategies/__init__.py`

## Adding a New Engine

1. Create a new file in `app/engines/`
2. Inherit from `BaseEngine`
3. Implement `run(strategy, df) -> EngineResult`
4. Register with `ENGINE_REGISTRY.register("id", EngineClass)`
5. Import in `app/engines/__init__.py`
