# Quant Terminal

A production-grade, multi-engine extensible full-stack quantitative trading terminal.

## Architecture

- **Backend**: Python + FastAPI (REST API + WebSocket)
- **Frontend**: React + Vite + TypeScript + TailwindCSS
- **Communication**: REST (configuration, triggers) + WebSocket (real-time progress, logs, results)

## Engines

| Engine      | Method                              | Objective            |
|-------------|-------------------------------------|----------------------|
| DRL         | PPO + Custom Gymnasium Environment  | Risk-adjusted return |
| Bayesian    | Optuna + Walk-Forward Validation    | Mean Calmar Ratio    |

## Strategies (12 Total)

1. Fibonacci Resonance
2. MAD Trend
3. Funding Arbitrage
4. PO3 Institutional
5. Order Flow Imbalance
6. MEV Capture
7. Statistical Pair Trading
8. NLP Event Driven
9. Dynamic Market Making
10. Liquidation Hunting
11. Liquidity Hedge Mining
12. Macro Capital Flow

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker-compose up --build
```

## Project Structure

```
crypto_quant_terminal/
  backend/         Python FastAPI backend
  frontend/        React + Vite frontend
  docker-compose.yml
```

## Design Principles

- **Registry Pattern**: Add strategies or engines by creating a file and registering it.
- **Walk-Forward Validation**: Prevents overfitting in Bayesian optimization.
- **Gaussian Noise Injection**: Prevents overfitting in DRL training.
- **Seed Fixation**: All random processes use fixed seeds for reproducibility.
- **Quick Mode**: Reduced computation for local development.
