# Backend - Crypto Quant Terminal

Python FastAPI backend providing REST API and WebSocket communication for the quantitative trading terminal.

## Architecture

```
app/
  main.py              FastAPI entry point
  config/config.py     Global configuration
  core/                Abstract base classes + registries
  strategies/          15 fully implemented strategies
  engines/             8 optimization engines (DRL, Bayesian, GA, Bandit, Volatility, Ensemble, MonteCarlo, RiskParity)
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

## Engines Overview

| ID | Name | Type | Purpose |
|----|------|------|---------|
| `drl` | Deep Reinforcement Learning (PPO) | Single/Multi | Learn optimal position sizing via neural network |
| `bayesian` | Bayesian Optimization (Optuna) | Single/Multi | Hyperparameter optimization with probabilistic search |
| `genetic` | Genetic Algorithm | Multi | Evolve strategy weights through crossover + mutation |
| `bandit` | Thompson Sampling Bandit | Multi | Online learning: adapt weights bar-by-bar via Beta distribution |
| `volatility` | Volatility Adaptive | Multi | Switch weights based on 3 volatility regimes (low/mid/high) |
| `ensemble` | Ensemble Learning | Multi | Each strategy independently optimized; IS Sharpe = expert weight |
| `montecarlo` | Monte Carlo Robustness | Multi | Parameter perturbation sampling; report Sharpe P5/median/std |
| `risk_parity` | Risk Parity | Multi | Weight strategies by inverse signal volatility for equal risk |

**Key Differences:**
- **Single-strategy engines**: Optimize one strategy independently (Bayesian only)
- **Multi-strategy engines**: Accept strategy lists and combine signals (DRL, GA, Bandit, Volatility, Ensemble, MonteCarlo, Risk Parity)
- **Online learning**: Bandit adapts weights continuously bar-by-bar
- **Robustness testing**: MonteCarlo estimates parameter sensitivity

## Adding a New Engine

1. Create a new file in `app/engines/`
2. Inherit from `BaseEngine`
3. Implement `run(strategy, df) -> EngineResult`
4. Register with `ENGINE_REGISTRY.register("id", EngineClass)`
5. Import in `app/engines/__init__.py`
6. Update routes.py if the engine accepts multiple strategies
