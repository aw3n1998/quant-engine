
import asyncio
import os
import logging
import pandas as pd

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("test_proxy")

async def test_binance_connection():
    # 1. 检查环境变量原始值
    raw_proxy = os.environ.get("all_proxy")
    logger.info(f"原始代理环境变量 (all_proxy): {repr(raw_proxy)}")
    
    if not raw_proxy:
        logger.error("未找到 all_proxy 环境变量，请确保启动时设置了它。")
        return

    # 2. 模拟我们之前的清洗逻辑
    # 这种清洗是为了应对 Windows 下常见的 \r \n 和引号问题
    clean_proxy = raw_proxy.replace("\"", "").replace("'", "").strip()
    clean_proxy = "".join(clean_proxy.split())
    
    # 转换协议为 http (ccxt 异步模式的最稳协议)
    if "socks5" in clean_proxy:
        clean_proxy = clean_proxy.replace("socks5h://", "http://").replace("socks5://", "http://")
    
    clean_proxy = clean_proxy.rstrip("/")
    logger.info(f"清洗后的代理 URL: {repr(clean_proxy)}")

    # 3. 关键修复测试：从 os.environ 中彻底删除原始变量，防止 aiohttp 自动读取
    for env_key in ["all_proxy", "ALL_PROXY", "https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"]:
        if env_key in os.environ:
            del os.environ[env_key]
    logger.info("已清空系统环境变量中的原始代理设置，仅使用手动配置的 proxy。")

    try:
        import ccxt.async_support as ccxt
    except ImportError:
        logger.error("未找到 ccxt 库")
        return

    exchange = ccxt.binance({
        "proxy": clean_proxy,
        "enableRateLimit": True,
        "timeout": 20000, # 20秒超时
    })

    try:
        logger.info(f"正在尝试拉取 BTC/USDT K线...")
        ohlcv = await exchange.fetch_ohlcv("BTC/USDT", "1h", limit=5)
        logger.info(f"成功! 拉取到 {len(ohlcv)} 根 K 线。")
        print("\n--- 数据预览 ---")
        for bar in ohlcv:
            print(bar)
    except Exception as e:
        logger.error(f"连接失败! 错误类型: {type(e).__name__}")
        logger.error(f"详细错误内容: {e}")
        
        # 如果还是 yarl 解析错误，尝试手动拆分 URL 检查
        if "yarl" in str(e) or "port" in str(e):
            try:
                from yarl import URL
                u = URL(clean_proxy)
                logger.info(f"Yarl 解析结果: Host={u.host}, Port={u.port}, Scheme={u.scheme}")
            except Exception as parse_err:
                logger.error(f"Yarl 手动解析也失败了: {parse_err}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(test_binance_connection())
