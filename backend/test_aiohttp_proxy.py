
import asyncio
import os
import logging
import aiohttp
from yarl import URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aiohttp_test")

async def test_direct_aiohttp():
    # 模拟环境变量
    proxy_url = "http://127.0.0.1:7897"
    
    # 彻底隔离测试：仅手动构造 URL
    target_url = "https://api.binance.com/api/v3/ping"
    
    logger.info(f"正在测试直接使用 aiohttp 访问币安 (代理: {proxy_url})...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # 这里的 proxy 参数是 aiohttp 报错的重灾区
            async with session.get(target_url, proxy=proxy_url, timeout=10) as resp:
                status = resp.status
                logger.info(f"连接成功! 响应码: {status}")
                json_data = await resp.json()
                logger.info(f"响应内容: {json_data}")
    except Exception as e:
        logger.error(f"aiohttp 测试失败: {type(e).__name__}: {e}")
        
        if "ValueError" in str(e):
            logger.info("捕获到了 ValueError! 正在分析 proxy_url 构造...")
            # 尝试另一种构造方式：使用 yarl.URL 对象
            try:
                proxy_obj = URL(proxy_url)
                logger.info(f"尝试使用 URL 对象替代字符串: {repr(proxy_obj)}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(target_url, proxy=proxy_obj, timeout=10) as resp:
                        logger.info(f"使用 URL 对象成功! 响应码: {resp.status}")
            except Exception as e2:
                logger.error(f"即使使用 URL 对象也失败了: {e2}")

if __name__ == "__main__":
    asyncio.run(test_direct_aiohttp())
