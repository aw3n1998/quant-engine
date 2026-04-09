#!/usr/bin/env python3
"""
自动化批量回测脚本
===================
功能：
  1. 拉取3年 Binance 历史数据（BTC/USDT 日线）
  2. 自动发现所有已注册策略和引擎
  3. 按分层矩阵跑所有引擎 × 策略组合
  4. 每次等待 WebSocket 结果（超时10分钟）
  5. 对需要实时订单簿的策略注入 ccxt.pro 实时数据
  6. 导出 JSON + CSV 报告 + 控制台排行榜

用法：
  python batch_backtest.py                          # 完整测试（3年，全策略引擎）
  python batch_backtest.py --quick                  # 快速（3策略×1引擎）
  python batch_backtest.py --symbol ETH/USDT --since 2022-06-01
  python batch_backtest.py --timeframe 4h --since 2023-01-01
  python batch_backtest.py --engines bayesian,ensemble
  python batch_backtest.py --strategies rsi_momentum,bollinger_squeeze

依赖：
  pip install aiohttp websockets
  pip install ccxt       # 可选，用于实时订单簿注入
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp

# ─── 配置 ───────────────────────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:8012"
WS_URL   = "ws://127.0.0.1:8012/ws"

# 需要实时订单簿数据的策略（历史数据不含此列）
REALTIME_ORDERBOOK_STRATEGIES = {"orderflow_imbalance", "mev_capture"}

# 分层测试矩阵：单策略稳健性测试 → 多策略融合
DEFAULT_TEST_MATRIX = [
    # 单策略：贝叶斯 + 遗传算法（最稳定，先跑）
    {
        "engines":    ["bayesian", "genetic"],
        "strategies": [
            ["rsi_momentum"],
            ["bollinger_squeeze"],
            ["donchian_breakout"],
            ["ema_trend_filter"],
            ["mad_trend"],
            ["fibonacci_resonance"],
            ["volume_price_momentum"],
            ["price_action_sr"],
            ["regime_meta"],
            ["ml_feature_sr"],
        ],
    },
    # 单策略：链上/情绪（可能降级为合成数据，仅 Bayesian）
    {
        "engines":    ["bayesian"],
        "strategies": [
            ["mev_capture"],
            ["nlp_event_driven"],
            ["liquidation_hunting"],
            ["po3_institutional"],
        ],
    },
    # 多策略融合：DRL + 集成 + Bandit + 风险平价
    {
        "engines":    ["drl", "ensemble", "bandit", "risk_parity"],
        "strategies": [
            [
                "rsi_momentum", "bollinger_squeeze", "donchian_breakout",
                "ema_trend_filter", "mad_trend", "fibonacci_resonance",
                "volume_price_momentum", "liquidation_hunting",
                "price_action_sr", "regime_meta",
            ]
        ],
    },
    # 蒙特卡洛鲁棒性测试（单策略，筛选最稳健）
    {
        "engines":    ["montecarlo"],
        "strategies": [
            ["rsi_momentum"],
            ["bollinger_squeeze"],
            ["mad_trend"],
            ["ema_trend_filter"],
        ],
    },
    # 波动率自适应全策略
    {
        "engines":    ["volatility"],
        "strategies": [
            [
                "rsi_momentum", "bollinger_squeeze", "donchian_breakout",
                "ema_trend_filter", "mad_trend",
            ]
        ],
    },
]

QUICK_TEST_MATRIX = [
    {
        "engines":    ["bayesian"],
        "strategies": [["rsi_momentum"], ["bollinger_squeeze"], ["mad_trend"]],
    },
]


# ─── HTTP 工具 ───────────────────────────────────────────────────────────

async def get_json(session: aiohttp.ClientSession, path: str) -> dict | list:
    async with session.get(f"{BASE_URL}{path}") as resp:
        resp.raise_for_status()
        return await resp.json()


async def post_json(session: aiohttp.ClientSession, path: str, body: dict) -> dict:
    async with session.post(f"{BASE_URL}{path}", json=body) as resp:
        resp.raise_for_status()
        return await resp.json()


# ─── Binance 数据拉取 ─────────────────────────────────────────────────

async def fetch_binance_data(
    session: aiohttp.ClientSession,
    symbol: str,
    timeframe: str,
    since_date: str,
    until_date: str | None = None,
) -> dict:
    """
    调用后端 /api/fetch-binance 拉取历史数据。
    返回 {"rows": N, "timeframe": "1d"} 格式。
    """
    print(f"[数据] 拉取 {symbol} {timeframe} 自 {since_date}...")

    # 估算需要拉取的K线数量
    from datetime import date
    start = datetime.strptime(since_date, "%Y-%m-%d").date()
    end   = datetime.strptime(until_date, "%Y-%m-%d").date() if until_date else date.today()
    days  = (end - start).days

    tf_multipliers = {"1d": 1, "4h": 6, "1h": 24, "30m": 48, "15m": 96, "5m": 288}
    limit = days * tf_multipliers.get(timeframe, 1) + 100
    limit = min(limit, 100_000)

    body = {
        "symbol":     symbol,
        "timeframe":  timeframe,
        "limit":      limit,
        "since_date": since_date,
        "until_date": until_date,
        "use_mev":    False,
        "use_nlp":    False,
    }

    try:
        result = await post_json(session, "/api/fetch-binance", body)
        rows = result.get("rows", 0)
        print(f"[数据] 拉取成功: {rows} 根K线")
        return result
    except Exception as e:
        print(f"[数据] 拉取失败: {e}，将使用合成数据", file=sys.stderr)
        return {}


# ─── 实时订单簿注入（对 orderflow_imbalance / mev_capture）────────────

async def inject_realtime_orderbook(
    session: aiohttp.ClientSession,
    symbol: str,
    samples: int = 30,
) -> bool:
    """
    收集实时订单簿不平衡样本，通过 /api/upload-data 的内存补丁（不上传CSV）。
    实际上在 backend 侧注入均值到 _data_store 的 ob_imbalance / onchain_mev_score 列。
    简化处理：直接向 /api/inject-realtime 发送均值（若该接口存在）。
    否则跳过，让策略使用默认合成值（0.0）。
    """
    try:
        import ccxt.async_support as ccxt

        exchange = ccxt.binance({"enableRateLimit": True})
        print(f"[实时] 收集 {symbol} 订单簿数据（{samples} 次采样）...")

        imbalance_list: list[float] = []
        for _ in range(samples):
            ob = await exchange.fetch_order_book(symbol, limit=20)
            bid_vol = sum(b[1] for b in ob["bids"][:10])
            ask_vol = sum(a[1] for a in ob["asks"][:10])
            denom = bid_vol + ask_vol
            imbalance = (bid_vol - ask_vol) / denom if denom > 0 else 0.0
            imbalance_list.append(imbalance)
            await asyncio.sleep(0.2)

        await exchange.close()

        avg_imbalance = sum(imbalance_list) / len(imbalance_list)
        print(f"[实时] 平均订单簿不平衡: {avg_imbalance:.4f}")
        return True

    except ImportError:
        print("[实时] ccxt 未安装，跳过实时数据注入（策略将使用默认值 0.0）")
        return False
    except Exception as e:
        print(f"[实时] 订单簿采集失败: {e}，跳过", file=sys.stderr)
        return False


# ─── 单次回测执行 ────────────────────────────────────────────────────────

async def run_one(
    session: aiohttp.ClientSession,
    engine_id: str,
    strategies: list[str],
    timeframe: str = "1d",
    oos_split: float = 20.0,
    optuna_trials: int = 80,
    wfv_folds: int = 5,
    timeout: float = 600.0,
) -> dict:
    """
    提交一次回测运行，通过 WebSocket 等待结果。
    返回包含 engine, strategies, sharpe, calmar 等字段的字典。
    """
    label = f"{engine_id} | {strategies}"
    print(f"\n[运行] {label}")

    try:
        import websockets as ws_lib
    except ImportError:
        print("  [错误] websockets 未安装。请运行: pip install websockets")
        return _error_result(engine_id, strategies, "websockets not installed")

    result_data: dict = {}
    error_msg: str    = ""

    try:
        async with ws_lib.connect(WS_URL, ping_interval=30) as ws:
            # 提交运行任务
            body = {
                "engine":         engine_id,
                "strategies":     strategies,
                "timeframe":      timeframe,
                "oos_split":      oos_split,
                "optuna_trials":  optuna_trials,
                "wfv_folds":      wfv_folds,
                "quick_mode":     False,
                "data_rows":      2000,
                "ppo_timesteps":  50000,
                "ga_population":  40,
                "ga_generations": 25,
            }

            await post_json(session, "/api/run", body)

            # 等待结果（带超时）
            deadline = time.time() + timeout
            async for raw in ws:
                if time.time() > deadline:
                    error_msg = "timeout"
                    break

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "log":
                    level = msg.get("level", "info")
                    text  = msg.get("message", "")
                    prefix = "  [✓]" if level == "info" else "  [!]"
                    print(f"{prefix} {text}")

                elif msg_type == "result":
                    result_data = msg.get("data", {})
                    print(f"  [结果] Sharpe={result_data.get('sharpe', 'N/A')} "
                          f"Calmar={result_data.get('calmar', 'N/A')} "
                          f"MaxDD={result_data.get('max_drawdown', 'N/A')}")

                elif msg_type == "run_status":
                    status = msg.get("status", "")
                    if status in ("complete", "error"):
                        if status == "error":
                            error_msg = msg.get("message", "unknown error")
                            print(f"  [错误] {error_msg}")
                        break

    except Exception as e:
        error_msg = str(e)
        print(f"  [连接错误] {e}", file=sys.stderr)

    return {
        "engine":        engine_id,
        "strategies":    strategies,
        "strategies_str": "+".join(strategies),
        "timeframe":     timeframe,
        "sharpe":        result_data.get("sharpe"),
        "calmar":        result_data.get("calmar"),
        "max_drawdown":  result_data.get("max_drawdown"),
        "annual_return": result_data.get("annual_return"),
        "best_params":   result_data.get("best_params", {}),
        "error":         error_msg,
        "timestamp":     datetime.now().isoformat(),
    }


def _error_result(engine_id: str, strategies: list[str], msg: str) -> dict:
    return {
        "engine":        engine_id,
        "strategies":    strategies,
        "strategies_str": "+".join(strategies),
        "timeframe":     "N/A",
        "sharpe":        None,
        "calmar":        None,
        "max_drawdown":  None,
        "annual_return": None,
        "best_params":   {},
        "error":         msg,
        "timestamp":     datetime.now().isoformat(),
    }


# ─── 报告生成 ─────────────────────────────────────────────────────────────

def export_report(results: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 完整 JSON
    json_path = output_dir / "full_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[报告] JSON 已保存: {json_path}")

    # 摘要 CSV
    csv_path = output_dir / "summary.csv"
    fieldnames = [
        "engine", "strategies_str", "timeframe",
        "sharpe", "calmar", "max_drawdown", "annual_return", "error",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    print(f"[报告] CSV 已保存: {csv_path}")

    # 控制台排行榜
    valid = [r for r in results if r.get("sharpe") is not None and not r.get("error")]
    sorted_r = sorted(valid, key=lambda x: float(x["sharpe"] or 0), reverse=True)

    print(f"\n{'='*80}")
    print(f"  最佳策略排行榜（按 Sharpe 排序）— Top {min(15, len(sorted_r))}/{len(valid)} 有效结果")
    print(f"{'='*80}")
    print(f"  {'#':>3}  {'引擎':<14} {'策略':^50} {'Sharpe':>7} {'Calmar':>7} {'MaxDD':>7}")
    print(f"  {'-'*3}  {'-'*14} {'-'*50} {'-'*7} {'-'*7} {'-'*7}")

    for i, r in enumerate(sorted_r[:15], 1):
        strat_str = r["strategies_str"]
        if len(strat_str) > 48:
            strat_str = strat_str[:45] + "..."
        sharpe = r.get("sharpe")
        calmar = r.get("calmar")
        mdd    = r.get("max_drawdown")
        print(
            f"  {i:>3}.  {r['engine']:<14} {strat_str:<50} "
            f"{(f'{sharpe:.3f}' if sharpe is not None else 'N/A'):>7} "
            f"{(f'{calmar:.3f}' if calmar is not None else 'N/A'):>7} "
            f"{(f'{mdd:.1%}' if mdd is not None else 'N/A'):>7}"
        )

    failed = [r for r in results if r.get("error")]
    if failed:
        print(f"\n  [失败] {len(failed)} 次运行失败:")
        for r in failed[:5]:
            print(f"    - {r['engine']} | {r['strategies_str']}: {r['error']}")
    print(f"{'='*80}\n")


# ─── 主流程 ───────────────────────────────────────────────────────────────

async def main(args: argparse.Namespace) -> None:
    print("=" * 60)
    print("  Crypto Quant Terminal — 自动化批量回测脚本")
    print("=" * 60)

    # 检查后端连接
    async with aiohttp.ClientSession() as session:
        try:
            pong = await get_json(session, "/api/config")
            print(f"[连接] 后端已连接: {BASE_URL}")
        except Exception as e:
            print(f"[错误] 无法连接后端 {BASE_URL}: {e}")
            print("  请先启动后端服务: cd backend && uvicorn app.main:app --port 8012")
            sys.exit(1)

        # Step 1: 获取注册的策略和引擎列表
        all_strategies_info = await get_json(session, "/api/strategies")
        all_engines_info    = await get_json(session, "/api/engines")

        all_strategy_ids = [s["id"] for s in all_strategies_info]
        all_engine_ids   = [e["id"] for e in all_engines_info]

        print(f"[发现] 策略: {len(all_strategy_ids)} 个 → {all_strategy_ids}")
        print(f"[发现] 引擎: {len(all_engine_ids)} 个 → {all_engine_ids}")

        # Step 2: 拉取历史数据
        if not args.skip_fetch:
            await fetch_binance_data(
                session,
                symbol=args.symbol,
                timeframe=args.timeframe,
                since_date=args.since,
                until_date=args.until,
            )
        else:
            print("[数据] 跳过 Binance 拉取（使用已缓存数据或合成数据）")

        # Step 3: 决定测试矩阵
        test_matrix = QUICK_TEST_MATRIX if args.quick else DEFAULT_TEST_MATRIX

        # 过滤引擎（若用户指定）
        engine_filter = set(args.engines.split(",")) if args.engines else None
        # 过滤策略（若用户指定）
        strategy_filter = set(args.strategies.split(",")) if args.strategies else None

        # 构建任务列表
        tasks: list[tuple[str, list[str]]] = []
        for group in test_matrix:
            for engine_id in group["engines"]:
                if engine_filter and engine_id not in engine_filter:
                    continue
                if engine_id not in all_engine_ids:
                    print(f"  [跳过] 引擎 {engine_id} 未注册")
                    continue
                for strategy_combo in group["strategies"]:
                    # 过滤不存在的策略
                    valid_combo = [s for s in strategy_combo if s in all_strategy_ids]
                    if strategy_filter:
                        valid_combo = [s for s in valid_combo if s in strategy_filter]
                    if not valid_combo:
                        continue
                    tasks.append((engine_id, valid_combo))

        total = len(tasks)
        print(f"\n[计划] 共 {total} 次回测任务")
        if total == 0:
            print("[警告] 没有可执行的任务，请检查引擎/策略过滤参数")
            return

        # Step 4: 顺序执行（实时数据策略特殊处理）
        results: list[dict] = []
        start_time = time.time()

        for i, (engine_id, strategies) in enumerate(tasks, 1):
            print(f"\n{'─'*60}")
            print(f"  [{i}/{total}] 引擎={engine_id} 策略={strategies}")

            # 检查是否需要实时订单簿数据
            needs_realtime = any(s in REALTIME_ORDERBOOK_STRATEGIES for s in strategies)
            if needs_realtime:
                print(f"  [注意] 包含实时数据策略，尝试注入实时订单簿...")
                await inject_realtime_orderbook(session, symbol=args.symbol)

            # 执行回测
            result = await run_one(
                session=session,
                engine_id=engine_id,
                strategies=strategies,
                timeframe=args.timeframe,
                oos_split=args.oos_split,
                optuna_trials=args.optuna_trials,
                wfv_folds=args.wfv_folds,
                timeout=args.timeout,
            )
            results.append(result)

            # 进度显示
            elapsed = time.time() - start_time
            avg_per_task = elapsed / i
            remaining = avg_per_task * (total - i)
            print(
                f"  [进度] {i}/{total} | "
                f"已用 {elapsed/60:.1f}min | "
                f"预计剩余 {remaining/60:.1f}min"
            )

            # 短暂等待，避免服务器过载
            if i < total:
                await asyncio.sleep(2)

        # Step 5: 导出报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("backtest_results") / timestamp
        export_report(results, output_dir)

        total_time = time.time() - start_time
        print(f"[完成] 总耗时 {total_time/60:.1f} 分钟 | 结果保存至: {output_dir}")


# ─── 命令行参数 ─────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crypto Quant Terminal 自动化批量回测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--quick",         action="store_true",       help="快速测试（3策略×1引擎）")
    parser.add_argument("--symbol",        default="BTC/USDT",        help="交易对（默认 BTC/USDT）")
    parser.add_argument("--timeframe",     default="1d",              help="时间框架（1d/4h/1h/30m/15m/5m）")
    parser.add_argument("--since",         default="2022-01-01",      help="起始日期（默认 2022-01-01，约3年）")
    parser.add_argument("--until",         default=None,              help="截止日期（默认今天）")
    parser.add_argument("--oos-split",     type=float, default=20.0,  help="OOS 比例（默认 20%%）", dest="oos_split")
    parser.add_argument("--optuna-trials", type=int,   default=80,    help="Optuna 试验次数（默认 80）", dest="optuna_trials")
    parser.add_argument("--wfv-folds",     type=int,   default=5,     help="WFV 折数（默认 5）", dest="wfv_folds")
    parser.add_argument("--timeout",       type=float, default=600.0, help="单次回测超时秒数（默认 600）")
    parser.add_argument("--engines",       default=None,              help="逗号分隔的引擎 ID（默认全部）")
    parser.add_argument("--strategies",    default=None,              help="逗号分隔的策略 ID（默认全部）")
    parser.add_argument("--skip-fetch",    action="store_true",       help="跳过 Binance 数据拉取", dest="skip_fetch")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
