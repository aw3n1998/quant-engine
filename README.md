# QuantEngine — 多引擎加密货币量化交易终端
# QuantEngine — Multi-Engine Crypto Quantitative Trading Terminal

> 赛博朋克风格的全栈量化回测与优化平台，集成深度强化学习、贝叶斯优化与遗传算法三大引擎，支持 12 种交易策略，实时 WebSocket 推送训练进度与结果。
>
> A cyberpunk-styled full-stack quantitative backtesting and optimization platform, integrating DRL, Bayesian Optimization, and Genetic Algorithm engines across 12 trading strategies with real-time WebSocket streaming.

---

## 系统功能概览 / System Overview

### 三大优化引擎 / Three Optimization Engines

| 引擎 / Engine | 算法 / Algorithm | 目标 / Objective | 适合场景 / Best For |
|---|---|---|---|
| **ENGINE A — DRL** | PPO (Proximal Policy Optimization) + 自定义 Gymnasium 环境 | 风险调整后收益最大化 | 无需调参，AI 自主学习最优仓位分配，新手首选 |
| **ENGINE B — Bayesian** | Optuna TPE + Walk-Forward Validation | 最大化平均 Calmar 比率 | 对特定策略进行系统性参数空间搜索 |
| **ENGINE C — Genetic Algorithm** | 两阶段遗传算法 + 适应度缓存 | 最优多策略因子权重组合 | 跨策略因子权重进化，追求组合极致优化 |

| Engine | Algorithm | Objective | Best For |
|---|---|---|---|
| **ENGINE A — DRL** | PPO + Custom Gymnasium Env | Risk-adjusted return | No-config AI portfolio learning; beginner-friendly |
| **ENGINE B — Bayesian** | Optuna TPE + Walk-Forward | Mean Calmar Ratio | Systematic parameter search for specific strategies |
| **ENGINE C — Genetic** | Two-phase GA + fitness cache | Optimal factor weight combo | Cross-strategy weight evolution for maximum alpha |

---

### 12 种交易策略 / 12 Trading Strategies

| ID | 中文名 | 说明 | English Name | Description |
|---|---|---|---|---|
| `fibonacci_resonance` | 斐波那契共振 | 利用黄金分割回调点捕捉趋势反转 | Fibonacci Resonance | Golden ratio retracement reversal signals |
| `mad_trend` | MAD 趋势跟随 | 均值绝对偏差突破，趋势延续策略 | MAD Trend | Mean Absolute Deviation breakout trend following |
| `funding_arbitrage` | 资金费率套利 | 利用永续合约与现货价差套利 | Funding Arbitrage | Perp vs spot funding rate differential capture |
| `po3_institutional` | 机构 PO3 模式 | 识别主力资金的积累-操控-分配周期 | PO3 Institutional | Accumulation-manipulation-distribution cycle detection |
| `orderflow_imbalance` | 订单流失衡 | 通过买卖盘不平衡预判价格方向 | Order Flow Imbalance | Bid/ask volume imbalance directional bias |
| `mev_capture` | MEV 捕获 | 捕获链上最大可提取价值机会（需链上数据）| MEV Capture | On-chain max extractable value (requires on-chain data) |
| `statistical_pair` | 统计配对 | 协整配对交易，均值回归策略 | Statistical Pair | Cointegration-based pair trading mean reversion |
| `nlp_event_driven` | NLP 事件驱动 | 基于市场情绪文本分析的事件交易（需 NLP 数据）| NLP Event Driven | Sentiment-based event trading (requires NLP feed) |
| `dynamic_market_making` | 动态做市 | 自适应买卖价差，通过流动性提供获利 | Dynamic Market Making | Adaptive spread liquidity provision |
| `liquidation_hunting` | 爆仓猎手 | 预判强平区域，跟随清算流动性 | Liquidation Hunting | Liquidation cluster prediction and cascade following |
| `liquidity_hedge_mining` | 流动性对冲挖矿 | DeFi 流动性池对冲 + 手续费挖矿 | Liquidity Hedge Mining | DeFi LP hedging with fee yield capture |
| `macro_capital_flow` | 宏观资本流 | 跟踪跨市场大资金流向的宏观策略 | Macro Capital Flow | Cross-market institutional flow tracking |

---

### 数据源 / Data Sources

| 数据源 | 说明 | Source | Description |
|---|---|---|---|
| **Synthetic** | 内置合成 K 线数据，快速本地测试，支持 500–20000 根 | Built-in synthetic OHLCV, 500–20,000 bars, no API needed |
| **CSV** | 上传自定义历史数据，支持大小写不敏感列名，自动识别 OHLCV | Custom CSV with case-insensitive column normalization |
| **Binance** | 通过 Binance REST API 实时拉取任意交易对 K 线，支持所有时间框架 | Live Binance REST fetch for any symbol and timeframe |

---

### 前端界面功能 / Frontend Features

- **赛博朋克终端风格** — 深绿 + 黑色 + 霓虹辉光设计，JetBrains Mono 字体，ASCII 边框窗口
- **实时训练监控** — DRL 训练期间实时双轴曲线（累计奖励 + 策略熵），WebSocket 推送
- **多结果对比** — 支持多次引擎运行结果并排对比（COMPARE Tab），Calmar/Sharpe 分组柱状图
- **策略权重可视化** — DRL/GA 策略权重时序堆积面积图
- **贝叶斯优化可视化** — Optuna 优化历史散点图 + 参数重要性柱状图
- **GA 收敛曲线** — 两阶段适应度收敛 + 种群标准差双轴图
- **指标评级系统** — 年化收益/Calmar/夏普/最大回撤四维自动评级（优秀/良好/尚可/偏低）
- **新手指南弹窗** — 三步上手教程 + 引擎对比表 + 指标速查
- **策略降级通知** — 检测到 MEV/NLP/订单流数据缺失时自动提示策略降级
- **历史记录面板** — 持久化所有回测结果，支持引擎完成后自动刷新
- **专家模式开关** — 默认隐藏高级参数（PPO Steps、WFV Folds），专家可按需展开

- **Cyberpunk terminal aesthetic** — dark green/black neon glow, JetBrains Mono, ASCII-bordered panels
- **Live training monitor** — real-time dual-axis DRL chart (reward + policy entropy) via WebSocket
- **Multi-result comparison** — side-by-side engine result COMPARE tab with grouped bar chart
- **Strategy weight visualization** — stacked area chart of DRL/GA weight dynamics over OOS period
- **Bayesian visualization** — Optuna optimization history + parameter importance bar chart
- **GA convergence chart** — two-phase fitness convergence + population std dual-axis plot
- **Metric rating system** — auto 4-level rating (优秀/良好/尚可/偏低) for all key metrics
- **Beginner help modal** — 3-step quickstart + engine comparison + metric glossary in Chinese
- **Strategy degradation alerts** — warns when MEV/NLP/order-flow data is zero-filled
- **History panel** — persistent run history with auto-refresh on engine completion
- **Expert mode toggle** — hides advanced params (PPO Steps, WFV Folds) by default

---

### 后端技术特性 / Backend Technical Features

- **Walk-Forward Validation (WFV)** — 扩展窗口时序交叉验证，防止参数过拟合。DRL 最多 3 折（避免数据切片过小），Bayesian/GA 支持 2–10 折可配置
- **热启动训练** — DRL 各 WFV 折之间保留策略权重（`set_env()` 热切换），显著减少训练时间
- **滑点模型** — 仓位变动按 5bps 扣除滑点成本，模拟真实交易摩擦
- **适应度缓存** — GA 将已评估染色体序列化为 `bytes` key 缓存，减少 30–40% 重复 WFV 计算
- **向量化信号生成** — MAD Trend 等策略使用 pandas 向量化替代逐行循环，提速 50–100x
- **策略注册表模式** — 新增策略只需创建文件并注册，无需修改引擎代码
- **固定随机种子** — 所有随机过程固定种子，结果完全可复现

- **Walk-Forward Validation** — expanding-window time-series CV prevents overfitting; DRL capped at 3 folds, Bayesian/GA configurable 2–10
- **Hot-start training** — DRL reuses policy weights across WFV folds via `set_env()` hot-swap
- **Slippage model** — 5bps slippage cost per unit position change simulates real trading friction
- **Fitness cache** — GA serializes chromosomes to `bytes` keys, skipping 30–40% redundant WFV evaluations
- **Vectorized signal generation** — pandas-vectorized strategies (e.g. MAD Trend) run 50–100x faster than loop equivalents
- **Registry pattern** — add strategies/engines by creating a file and registering; no engine code changes
- **Fixed seeds** — all stochastic processes use fixed seeds for full reproducibility

---

## 性能指标说明 / Performance Metrics Explained

| 指标 | 说明 | 参考值 | Metric | Description | Reference |
|---|---|---|---|---|---|
| Annual Return | 年化收益率 | ≥30% 优秀 | Annual Return | Annualized total return | ≥30% excellent |
| Max Drawdown | 历史最大亏损幅度（负值越小越好）| ≥-5% 优秀 | Max Drawdown | Peak-to-trough decline | ≥-5% excellent |
| Sharpe Ratio | 风险调整后超额收益 | ≥2 优秀 | Sharpe Ratio | Return per unit of risk | ≥2 excellent |
| Calmar Ratio | 年化收益 ÷ 最大回撤 | ≥1.5 优秀 | Calmar Ratio | Annual return / max drawdown | ≥1.5 excellent |

---

## 快速启动 / Quick Start

### 后端 / Backend

```bash
cd backend
pip install -r requirements.txt

# 配置环境变量（可选，Binance 数据需要）
cp .env.example .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8012
```

### 前端 / Frontend

```bash
cd frontend
npm install
npm run dev
# 访问 / Open: http://localhost:5173
```

### Docker

```bash
docker-compose up --build
```

---

## 项目结构 / Project Structure

```
quantEngine/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py          # REST + WebSocket 端点
│   │   ├── config/
│   │   │   └── config.py          # 全局配置（Pydantic）
│   │   ├── engines/
│   │   │   ├── drl_engine.py      # PPO 深度强化学习引擎
│   │   │   ├── bayesian_engine.py # Optuna 贝叶斯优化引擎
│   │   │   └── genetic_engine.py  # 两阶段遗传算法引擎
│   │   ├── envs/
│   │   │   └── crypto_portfolio_env.py  # Gymnasium 交易环境
│   │   ├── strategies/            # 12 种策略实现
│   │   └── utils/
│   │       └── metrics.py         # 回测指标计算
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/                # 组件库（TerminalSection, GlowButton, NeonInput…）
│   │   │   ├── ControlPanel.tsx   # 参数配置 + 引擎启动
│   │   │   ├── PerformanceArena.tsx  # 结果展示 + 图表
│   │   │   ├── HistoryPanel.tsx   # 历史记录
│   │   │   └── Singularity.tsx    # CSS 磁场球状态指示器
│   │   ├── data/
│   │   │   └── glossary.ts        # 策略中文名称库
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts    # WebSocket 状态管理
│   │   ├── pages/
│   │   │   └── Dashboard.tsx      # 主页面布局
│   │   └── utils/
│   │       └── plotTheme.ts       # 统一 Plotly 主题
│   └── package.json
└── docker-compose.yml
```

---

## 技术栈 / Tech Stack

**Backend:** Python 3.11 · FastAPI · Stable-Baselines3 (PPO) · Gymnasium · Optuna · NumPy · Pandas

**Frontend:** React 18 · TypeScript · Vite · TailwindCSS · Plotly.js · WebSocket

**Communication:** REST API (配置/触发) + WebSocket (实时日志/进度/结果)

---

## 设计原则 / Design Principles

- **注册表模式** — 新增策略创建文件即可，引擎自动发现，零侵入
- **时序数据完整性** — Walk-Forward 确保所有验证在纯样本外数据上进行
- **实时反馈** — WebSocket 推送训练进度、日志、结果，无需轮询
- **可复现性** — 固定随机种子确保相同参数下结果一致
- **新手友好** — 中文策略名、指标评级、新手引导弹窗，无量化经验也可上手

- **Registry pattern** — zero-boilerplate strategy/engine addition
- **Time-series integrity** — all validation strictly on out-of-sample data
- **Real-time feedback** — WebSocket eliminates polling; live progress on every step
- **Reproducibility** — fixed seeds across all stochastic components
- **Beginner-friendly** — Chinese strategy names, metric ratings, help modal for non-quant users
