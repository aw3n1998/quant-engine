# 环境变量配置指南

## 快速开始

### 1. 配置 WorldNews API Key

复制 `.env.example` 文件创建 `.env`：

```bash
cp .env.example .env
```

### 2. 编辑 `.env` 文件

```
# World News API Configuration
# 从 https://worldnewsapi.com/register 获取免费 API Key
WORLDNEWS_API_KEY=bd472aaa5d104b2cb25816fa8ee1b273

# Flashbots Configuration (公开API，无需Key)
FLASHBOTS_ENABLED=true

# Database Configuration
DB_PATH=data/quant_engine.db
```

将 `WORLDNEWS_API_KEY` 替换为您的实际 API Key。

### 3. 验证配置

重启后端服务，使 `.env` 配置生效：

```bash
cd backend
pip install -r requirements.txt  # 安装 python-dotenv
python -m uvicorn app.main:app --reload
```

### 4. 前端使用

在 Dashboard 中：

1. 选择数据源：**Binance**
2. 选择交易对：例如 **BTC/USDT**
3. 选择时间框架：例如 **5m**（日内交易推荐）
4. **启用 MEV**：✓（无需 Key，使用公开 Flashbots API）
5. **启用 NLP**：✓
   - API Key 输入框：**留空**（使用后端配置的默认 Key）
   - 或输入自己的 Key 覆盖默认配置
6. 点击 **[拉取数据]**

### 5. 验证成功

成功信息示例：
```
✓ 已加载 BTC/USDT 1h × 2160 根K线 (2024-01-01 ~ 2024-03-30) [MEV✓ NLP✓]
```

## 配置详解

### WORLDNEWS_API_KEY
- **获取方式**：https://worldnewsapi.com/register
- **用途**：拉取加密货币新闻并计算情绪评分 [-1, 1]
- **免费层限制**：每天 1000 次请求
- **可选**：前端可留空使用此默认 Key，或输入自己的 Key

### FLASHBOTS_ENABLED
- **默认值**：true
- **用途**：启用 Flashbots Boost Relay API（公开，无需 Key）
- **覆盖范围**：最近 30~60 天的链上 MEV 数据

### DB_PATH
- **默认值**：data/quant_engine.db
- **用途**：SQLite 数据库路径，存储运行历史和持久化数据

## 故障排查

### 问题：NLP 拉取失败

**错误**：`worldnews_api_key 为空或无效`

**解决**：
1. 确保 `.env` 文件中有正确的 WORLDNEWS_API_KEY
2. 确保后端已重启（读取新的 .env 配置）
3. 在前端输入框中输入 Key 作为覆盖

### 问题：MEV 数据全为 0

**原因**：可能是 Flashbots API 临时不可用或数据延迟

**解决**：
- 检查网络连接
- 稍后重试
- 策略有自动降级逻辑，会切换到 ATR 突破策略

### 问题：导入 python-dotenv 失败

**错误**：`ModuleNotFoundError: No module named 'dotenv'`

**解决**：
```bash
pip install python-dotenv>=1.0.0
```

## 安全建议

1. **不要提交 `.env` 文件到 Git**
   - `.gitignore` 已配置排除 `.env`
   - 但请确认 `.env` 不在 git 追踪中：
   ```bash
   git rm --cached backend/.env  # 如果误提交过
   ```

2. **API Key 保护**
   - 不要在代码、日志或控制台输出中暴露 API Key
   - 后端在调用 WorldNewsAPI 时使用配置的 Key，前端不保存敏感信息

3. **定期轮转 Key**
   - 如果怀疑 Key 泄露，在 WorldNewsAPI 控制台重新生成

## 扩展配置

未来可添加其他环境变量：

```bash
# Redis 缓存（可选）
REDIS_URL=redis://localhost:6379

# 日志级别
LOG_LEVEL=INFO

# 最大并发请求数
MAX_CONCURRENT_REQUESTS=10
```

更新 `config.py` 的 `AppConfig` 类即可自动读取这些变量。
