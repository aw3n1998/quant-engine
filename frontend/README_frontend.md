# Frontend - Crypto Quant Terminal

React + Vite + TypeScript + TailwindCSS frontend for the quantitative trading terminal.

## Architecture

```
src/
  App.tsx              Root component with navigation
  main.tsx             React entry point
  index.css            Global styles + Tailwind directives
  components/          Reusable UI components
    ControlPanel.tsx   Engine/strategy selection + run controls
    PerformanceArena.tsx  Equity curves + comparison table
    MetricCard.tsx     Individual metric display card
  pages/               Page-level components
    Dashboard.tsx      Main dashboard with control + results
    StrategyLibrary.tsx  Strategy catalog with search
    EngineRunner.tsx   Engine details and feature lists
  hooks/
    useWebSocket.ts    WebSocket connection with auto-reconnect
  services/
    api.ts             REST API client functions
  types/
    index.ts           TypeScript type definitions
  utils/
    formatters.ts      Number/percent/time formatting utilities
```

## Quick Start

```bash
npm install
npm run dev
```

The dev server runs on port 5173 with proxy to backend at port 8000.

## Features

- Real-time WebSocket connection with auto-reconnect
- Multi-engine strategy execution control
- Equity curve visualization (Recharts)
- Side-by-side performance comparison table
- Strategy library with search
- CSV data upload
- Quick Mode toggle for faster local testing
- Dark theme with glassmorphism design
