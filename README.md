# Crypto Quant Terminal — 完整指南

一个企业级的加密货币量化交易平台，配备 8 个优化引擎、15 个交易策略、自动化批量回测和实时 WebSocket 通信。

---

## 🚀 最新特性 (v2.1.0 - 2026-04-14)

* **🟢 高可靠 WebSocket**：内置 30 秒心跳保活（Ping-Pong）与指数退避（Exponential Backoff）断线重连机制，确保训练进度和日志推送稳定。
* **⚡ 高性能计算加速**：核心指标（如 EMA, RMA, RSI）底层已通过 Numba JIT 编译重写，极大提升了 Optuna 和 GA 在海量参数搜索时的运算速度。
* **📈 因子归因分析增强**：`PerformanceArena` 新增 **Alpha**（超额收益）与 **Beta**（市场相关性）的直观展示与图表评级，便于剥离 Beta 寻找纯 Alpha 策略。
* **📊 前端渲染优化**：历史回测面板（History Panel）已实装前端虚拟分页（Pagination），轻松应对千次以上的批量测试结果而不卡顿页面。
* **🤖 自动化与工程化**：
  * 全面集成 GitHub Actions **CI/CD 流水线**（自动执行 Pytest, Mypy 及前端 Build）。
  * 完善了基于 FastAPI 的 **OpenAPI/Swagger 文档**，包含详细的分组元数据（System, Market Data, Trading Engine 等）。
* **✅ 测试覆盖度**：核心业务逻辑、指标计算、异常处理 100% 通过（42个单元测试）。

---

## 快速启动

### 1. 后端启动（FastAPI）

```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端将在 `http://127.0.0.1:8000` 启动，提供 REST API 和 WebSocket 接口。
您可以在 `http://127.0.0.1:8000/docs` 查看交互式 API 文档。

### 2. 前端启动（React + Vite）

```bash
cd frontend
npm install
npm run dev
```

前端将在 `http://127.0.0.1:5173` 启动，自动代理到后端。

### 3. 访问应用

打开浏览器访问 http://127.0.0.1:5173

---

## 核心功能

### 🏠 Dashboard（主界面）

- **左侧 TERMINAL CONSOLE**：策略选择、引擎配置、快速回测
- **中间 PERFORMANCE ARENA**：净值曲线、因子权重分布、Alpha/Beta归因、实时日志
- **右侧 HISTORY PANEL**：历史回测结果分页、详细参数、OOS 验证

### 📊 8 个优化引擎

| 引擎 | 类型 | 优势 | 适用场景 |
|------|------|------|---------|
| **DRL (PPO)** | 深度强化学习 | 自主学习最优仓位、无需手调参数 | 新手友好，追求黑箱最优解 |
| **Bayesian (Optuna)** | 贝叶斯优化 | 高效搜索、概率建模、防过拟合 | 有策略偏好的用户 |
| **Genetic Algorithm** | 遗传算法 | 全局搜索、进化权重 | 多策略融合优化 |
| **Thompson Sampling (Bandit)** | 在线学习 | 实时适应、逐根K线更新 | 自适应系统、在线学习 |
| **Volatility Adaptive** | 波动率分档 | 自动切换防御/进攻模式 | 不同市场环境适应 |
| **Ensemble** | 集成学习 | 透明权重、快速融合 | 多专家投票 |
| **Monte Carlo** | 鲁棒性测试 | 参数敏感性分析 | 识别过拟合风险 |
| **Risk Parity** | 风险平价 | 等风险贡献、稳健性强 | 追求风险均衡 |

### 🎯 15 个交易策略

#### 纯 K 线策略（最稳定，已接入 Numba 加速）
- **Bollinger Squeeze**：布林带压缩 → 爆破方向预测
- **Donchian Breakout**：N 日高/低点突破 + ATR 过滤
- **EMA Trend Filter**：快/中/慢 EMA 三条线组合
- **MAD Trend**：平均绝对偏差自适应通道
- **RSI Momentum**：RSI 中轴穿越 + 极值回望确认
- **Fibonacci Resonance**：38.2%/50%/61.8% 回撤位反转
- **Volume Price Momentum**：成交量与价格协同性驱动

#### 链上/情绪策略（需数据支持）
- **MEV Capture**：追踪链上 MEV 活跃度
- **Orderflow Imbalance**：监测买卖单失衡程度
- **PO3 Institutional**：追踪机构持仓浓度
- **NLP Event Driven**：新闻情绪 + 成交量放大
- **Liquidation Hunting**：识别清算级联反弹

#### 高级策略（自适应/ML）
- **Regime Meta**：4 状态市场自适应（牛市/熊市/盘整/恐慌）
- **ML Feature SR**：RandomForest 工程特征 + 滚动重训练
- **Price Action SR**：历史高低点支阻反转

---

## 📈 自动化批量回测

完全自动化测试所有引擎 × 策略组合，无需手动点击。

### 快速测试（5 分钟内）

```bash
cd backend
python batch_backtest.py --quick
```

测试 3 个策略 × 1 个引擎（快速验证功能）。

### 完整 3 年回测

```bash
cd backend
python batch_backtest.py --since 2022-01-01
```

使用 Binance 真实数据，测试所有引擎 × 策略组合。

### 输出结果

```
backtest_results/
└── 20250409_143000/
    ├── full_results.json     # 完整原始数据
    ├── summary.csv           # 摘要表格
    └── console output        # 排行榜
```

---

## 🎮 使用流程

### 基础工作流

1. **选择数据源**
   - Synthetic（合成，快速）
   - CSV（上传自定义数据）
   - Binance（真实历史数据）

2. **选择时间框架** → 1d / 4h / 1h / 30m / 15m / 5m

3. **选择策略** → 可多选

4. **选择引擎** → 点击对应 ENGINE 按钮运行

5. **监控进度** → 中间面板实时显示日志、净值曲线、权重

6. **查看结果** → 右侧 HISTORY PANEL 显示历史记录与对比

---

## ⚙️ 配置

### 后端配置（`backend/.env`）

```env
API_PORT=8000
BINANCE_API_KEY=xxx
WORLDNEWS_API_KEY=xxx
```

---

## 🔧 添加新策略

1. 创建 `backend/app/strategies/my_strategy.py`
2. 继承 `BaseStrategy`，实现 `get_param_space()` 和 `generate_signals()`
3. 在 `backend/app/strategies/__init__.py` 导入
4. 在 `frontend/src/data/glossary.ts` 添加元数据

详见 `backend/README_backend.md`

---

## 🐛 常见问题

1. **后端连接失败** → 确保运行在正确的环境并开放了端口 `uvicorn app.main:app --port 8000`。
2. **Sharpe=∞ / Calmar=-inf** → 通常是由于时间框架（Timeframe）导致的数据量太小或无交易信号，请增加数据行数或使用合理的 OOS 比例。
3. **批量回测报错 429** → 触发了外部 API 频率限制，可以增加延时。

---

## 支持

- 📖 `backend/README_backend.md` - 后端文档
- 🎨 `frontend/README_frontend.md` - 前端文档
- 🚀 `backend/batch_backtest.py --help` - 批量回测帮助

---

**最后更新：2026-04-14**
版本: 2.1.0（性能与可靠性升级）
