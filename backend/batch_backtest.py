#!/usr/bin/env python3
"""
自动化批量回测脚本（并发版）
==============================
功能：
  - 拉取3年 Binance 历史数据
  - 矩阵测试所有引擎 × 策略组合
  - --workers N：多后端端口并发（每个 worker 独占一个后端实例）
  - --limit N：最多跑 N 个组合（防止跑太久）
  - --timeout-total N：全局时间限制（分钟）
  - --shuffle：随机打乱测试顺序
  - --resume：从上次断点续跑

用法：
  # 顺序测试（最安全）
  python batch_backtest.py --quick --limit 5

  # 多后端并发（先开 3 个后端实例）
  #   终端1: uvicorn app.main:app --port 8012
  #   终端2: uvicorn app.main:app --port 8013
  #   终端3: uvicorn app.main:app --port 8014
  python batch_backtest.py --workers 3

  # 其他常用选项
  python batch_backtest.py --since 2022-01-01 --symbol BTC/USDT
  python batch_backtest.py --timeout-total 30   # 30分钟后停止
  python batch_backtest.py --resume             # 续跑上次断点
  python batch_backtest.py --shuffle --limit 20 # 随机抽20个

依赖：
  pip install aiohttp websockets
  pip install ccxt   # 可选，实时订单簿注入
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp

# ─── 默认配置 ─────────────────────────────────────────────────────────
DEFAULT_PORT     = 8012
BASE_URL_TPL     = "http://127.0.0.1:{port}"
WS_URL_TPL       = "ws://127.0.0.1:{port}/ws"
CHECKPOINT_FILE  = Path("backtest_results/checkpoint.json")

REALTIME_ORDERBOOK_STRATEGIES = {"orderflow_imbalance", "mev_capture"}

# ─── 分层测试矩阵 ──────────────────────────────────────────────────────
DEFAULT_TEST_MATRIX = [
    # 单策略 × 快速引擎（最稳定，先跑）
    {
        "engines": ["bayesian"],
        "strategies": [
            ["rsi_momentum"], ["bollinger_squeeze"], ["donchian_breakout"],
            ["ema_trend_filter"], ["mad_trend"], ["fibonacci_resonance"],
            ["volume_price_momentum"], ["price_action_sr"],
            ["regime_meta"], ["ml_feature_sr"],
        ],
    },
    # 单策略 × 遗传算法
    {
        "engines": ["genetic"],
        "strategies": [
            ["rsi_momentum"], ["bollinger_squeeze"], ["mad_trend"], ["ema_trend_filter"],
        ],
    },
    # 链上/情绪策略（可能降级）
    {
        "engines": ["bayesian"],
        "strategies": [
            ["mev_capture"], ["nlp_event_driven"],
            ["liquidation_hunting"], ["po3_institutional"],
        ],
    },
    # 多策略融合
    {
        "engines": ["drl", "ensemble", "bandit", "risk_parity", "volatility"],
        "strategies": [
            ["rsi_momentum", "bollinger_squeeze", "donchian_breakout",
             "ema_trend_filter", "mad_trend", "fibonacci_resonance",
             "volume_price_momentum", "liquidation_hunting",
             "price_action_sr", "regime_meta"],
        ],
    },
    # 蒙特卡洛鲁棒性
    {
        "engines": ["montecarlo"],
        "strategies": [
            ["rsi_momentum"], ["bollinger_squeeze"], ["mad_trend"],
        ],
    },
]

QUICK_TEST_MATRIX = [
    {
        "engines": ["bayesian"],
        "strategies": [["rsi_momentum"], ["bollinger_squeeze"], ["mad_trend"]],
    },
]


# ─── HTTP 工具 ─────────────────────────────────────────────────────────

async def get_json(session: aiohttp.ClientSession, url: str) -> dict | list:
    async with session.get(url) as r:
        r.raise_for_status()
        return await r.json()


async def post_json(session: aiohttp.ClientSession, url: str, body: dict) -> dict:
    async with session.post(url, json=body) as r:
        r.raise_for_status()
        return await r.json()


# ─── Binance 数据拉取 ──────────────────────────────────────────────────

async def fetch_binance_data(
    session: aiohttp.ClientSession,
    base_url: str,
    symbol: str,
    timeframe: str,
    since_date: str,
    until_date: str | None,
) -> None:
    from datetime import date
    start = datetime.strptime(since_date, "%Y-%m-%d").date()
    end   = datetime.strptime(until_date, "%Y-%m-%d").date() if until_date else date.today()
    days  = (end - start).days
    tf_mul = {"1d": 1, "4h": 6, "1h": 24, "30m": 48, "15m": 96, "5m": 288}
    limit = min(days * tf_mul.get(timeframe, 1) + 100, 100_000)

    print(f"[数据] 拉取 {symbol} {timeframe} 自 {since_date}（约 {limit} 根K线）...")
    body = {
        "symbol": symbol, "timeframe": timeframe, "limit": limit,
        "since_date": since_date, "until_date": until_date,
        "use_mev": False, "use_nlp": False,
    }
    try:
        r = await post_json(session, f"{base_url}/api/fetch-binance", body)
        print(f"[数据] 拉取成功: {r.get('rows', '?')} 根K线")
    except Exception as e:
        print(f"[数据] 拉取失败: {e}，使用合成数据", file=sys.stderr)


# ─── 实时订单簿（可选）────────────────────────────────────────────────

async def inject_realtime_orderbook(symbol: str, samples: int = 30) -> None:
    try:
        import ccxt.async_support as ccxt
        ex = ccxt.binance({"enableRateLimit": True})
        print(f"[实时] 采集 {symbol} 订单簿（{samples} 次）...")
        vals = []
        for _ in range(samples):
            ob = await ex.fetch_order_book(symbol, limit=20)
            bv = sum(b[1] for b in ob["bids"][:10])
            av = sum(a[1] for a in ob["asks"][:10])
            vals.append((bv - av) / (bv + av) if bv + av > 0 else 0.0)
            await asyncio.sleep(0.2)
        await ex.close()
        avg = sum(vals) / len(vals)
        print(f"[实时] 平均订单簿失衡: {avg:.4f}")
    except ImportError:
        print("[实时] ccxt 未安装，跳过（策略使用默认值 0.0）")
    except Exception as e:
        print(f"[实时] 采集失败: {e}", file=sys.stderr)


# ─── 单次回测执行 ──────────────────────────────────────────────────────

async def run_one(
    session: aiohttp.ClientSession,
    base_url: str,
    ws_url: str,
    engine_id: str,
    strategies: list[str],
    args: argparse.Namespace,
    worker_id: int = 0,
) -> dict:
    prefix = f"[W{worker_id}]" if args.workers > 1 else ""
    label  = f"{engine_id} | {'+'.join(strategies)}"
    print(f"\n{prefix}[运行] {label}")

    try:
        import websockets as ws_lib
    except ImportError:
        print("  pip install websockets  先安装依赖")
        return _err(engine_id, strategies, "websockets not installed")

    result_data: dict = {}
    error_msg: str    = ""

    try:
        async with ws_lib.connect(ws_url, ping_interval=30) as ws:
            body = {
                "engine": engine_id, "strategies": strategies,
                "timeframe": args.timeframe, "oos_split": args.oos_split,
                "optuna_trials": args.optuna_trials, "wfv_folds": args.wfv_folds,
                "quick_mode": False, "data_rows": 2000, "ppo_timesteps": 50000,
                "ga_population": 40, "ga_generations": 25,
            }
            await post_json(session, f"{base_url}/api/run", body)

            deadline = time.time() + args.timeout
            async for raw in ws:
                if time.time() > deadline:
                    error_msg = "timeout"
                    break
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue

                t = msg.get("type", "")
                if t == "log":
                    lvl  = msg.get("level", "info")
                    text = msg.get("message", "")
                    icon = "✓" if lvl == "info" else "!"
                    print(f"  {prefix}[{icon}] {text}")
                elif t == "result":
                    result_data = msg.get("data", {})
                    sh = result_data.get("sharpe", "?")
                    ca = result_data.get("calmar", "?")
                    print(f"  {prefix}[结果] Sharpe={sh}  Calmar={ca}")
                elif t == "run_status" and msg.get("status") in ("complete", "error"):
                    if msg.get("status") == "error":
                        error_msg = msg.get("message", "error")
                    break
    except Exception as e:
        error_msg = str(e)
        print(f"  {prefix}[错误] {e}", file=sys.stderr)

    return {
        "engine":        engine_id,
        "strategies":    strategies,
        "strategies_str": "+".join(strategies),
        "timeframe":     args.timeframe,
        "worker":        worker_id,
        "sharpe":        result_data.get("sharpe"),
        "calmar":        result_data.get("calmar"),
        "max_drawdown":  result_data.get("max_drawdown"),
        "annual_return": result_data.get("annual_return"),
        "best_params":   result_data.get("best_params", {}),
        "error":         error_msg,
        "timestamp":     datetime.now().isoformat(),
    }


def _err(engine_id: str, strategies: list[str], msg: str) -> dict:
    return {
        "engine": engine_id, "strategies": strategies,
        "strategies_str": "+".join(strategies), "timeframe": "N/A",
        "worker": 0, "sharpe": None, "calmar": None, "max_drawdown": None,
        "annual_return": None, "best_params": {}, "error": msg,
        "timestamp": datetime.now().isoformat(),
    }


# ─── checkpoint 工具 ──────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"completed": [], "results": []}


def save_checkpoint(completed: list, results: list) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(
        json.dumps({"completed": completed, "results": results,
                    "timestamp": datetime.now().isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─── worker 协程 ─────────────────────────────────────────────────────

async def worker_loop(
    worker_id: int,
    port: int,
    tasks: list[tuple[str, list[str]]],
    args: argparse.Namespace,
    results: list,
    completed: list,
    lock: asyncio.Lock,
    global_start: float,
) -> None:
    base_url = BASE_URL_TPL.format(port=port)
    ws_url   = WS_URL_TPL.format(port=port)

    async with aiohttp.ClientSession() as session:
        for engine_id, strategies in tasks:
            # 检查全局超时
            if args.timeout_total and (time.time() - global_start) > args.timeout_total * 60:
                print(f"[W{worker_id}] 已达全局时间限制，停止")
                break

            key = f"{engine_id}|{'+'.join(strategies)}"

            async with lock:
                if key in completed:
                    print(f"[W{worker_id}] 跳过（已完成）: {key}")
                    continue

            # 实时数据注入
            if any(s in REALTIME_ORDERBOOK_STRATEGIES for s in strategies):
                await inject_realtime_orderbook(args.symbol)

            result = await run_one(
                session, base_url, ws_url, engine_id, strategies, args, worker_id,
            )

            async with lock:
                results.append(result)
                completed.append(key)
                done  = len(completed)
                total = len(tasks) * args.workers  # 近似
                elapsed = time.time() - global_start
                avg = elapsed / max(done, 1)
                print(
                    f"  [进度] {done} 完成 | "
                    f"已用 {elapsed/60:.1f}min | "
                    f"均速 {avg:.0f}s/次"
                )
                save_checkpoint(completed, results)

            # 同一 worker 任务间短暂间隔
            await asyncio.sleep(2)


# ─── 报告生成 ─────────────────────────────────────────────────────────

def export_report(results: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "full_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    fields = ["engine", "strategies_str", "timeframe", "sharpe",
              "calmar", "max_drawdown", "annual_return", "worker", "error"]
    with open(output_dir / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)

    # 排行榜
    valid = sorted(
        [r for r in results if r.get("sharpe") is not None and not r.get("error")],
        key=lambda x: float(x["sharpe"] or 0), reverse=True,
    )
    failed = [r for r in results if r.get("error")]

    print(f"\n{'='*78}")
    print(f"  最佳策略排行榜（按 Sharpe 排序）— Top {min(15, len(valid))}/{len(valid)} 有效")
    print(f"{'='*78}")
    print(f"  {'#':>3}  {'引擎':<14} {'策略':<42} {'Sharpe':>7} {'Calmar':>7} {'MaxDD':>7}")
    print(f"  {'-'*3}  {'-'*14} {'-'*42} {'-'*7} {'-'*7} {'-'*7}")
    for i, r in enumerate(valid[:15], 1):
        st = r["strategies_str"]
        if len(st) > 40: st = st[:37] + "..."
        sh = f"{r['sharpe']:.3f}"  if r.get("sharpe")       is not None else "N/A"
        ca = f"{r['calmar']:.3f}"  if r.get("calmar")        is not None else "N/A"
        dd = f"{r['max_drawdown']:.1%}" if r.get("max_drawdown") is not None else "N/A"
        print(f"  {i:>3}.  {r['engine']:<14} {st:<42} {sh:>7} {ca:>7} {dd:>7}")

    if failed:
        print(f"\n  [失败] {len(failed)} 次:")
        for r in failed[:5]:
            print(f"    - {r['engine']} | {r['strategies_str']}: {r['error']}")
    print(f"{'='*78}\n")
    print(f"[报告] {output_dir}/summary.csv")
    print(f"[报告] {output_dir}/full_results.json")


# ─── 主流程 ──────────────────────────────────────────────────────────

async def main(args: argparse.Namespace) -> None:
    print("=" * 60)
    print("  Crypto Quant Terminal — 批量回测脚本（并发版）")
    print(f"  workers={args.workers}  limit={args.limit or '∞'}  "
          f"timeout-total={args.timeout_total or '∞'}min")
    print("=" * 60)

    # 解析端口列表
    if args.ports:
        ports = [int(p.strip()) for p in args.ports.split(",")]
    else:
        ports = [DEFAULT_PORT + i for i in range(args.workers)]

    if len(ports) < args.workers:
        print(f"[警告] workers={args.workers} 但只给了 {len(ports)} 个端口，自动补全")
        while len(ports) < args.workers:
            ports.append(ports[-1] + 1)

    # 检查所有后端连接
    print(f"[连接] 检查 {args.workers} 个后端...")
    for port in ports[:args.workers]:
        base = BASE_URL_TPL.format(port=port)
        async with aiohttp.ClientSession() as s:
            try:
                await get_json(s, f"{base}/api/config")
                print(f"  ✓ {base}")
            except Exception as e:
                print(f"  ✗ {base}: {e}")
                print(f"    请先启动: uvicorn app.main:app --port {port}")
                sys.exit(1)

    # 获取策略/引擎列表（从第一个后端）
    base0 = BASE_URL_TPL.format(port=ports[0])
    async with aiohttp.ClientSession() as s:
        all_strat = await get_json(s, f"{base0}/api/strategies")
        all_eng   = await get_json(s, f"{base0}/api/engines")

    valid_strats = {x["id"] for x in all_strat}
    valid_engs   = {x["id"] for x in all_eng}
    print(f"[发现] {len(valid_strats)} 策略 | {len(valid_engs)} 引擎")

    # 拉取历史数据（每个后端独立拉取）
    if not args.skip_fetch:
        async with aiohttp.ClientSession() as s:
            for port in ports[:args.workers]:
                base = BASE_URL_TPL.format(port=port)
                await fetch_binance_data(
                    s, base, args.symbol, args.timeframe,
                    args.since, args.until,
                )

    # 构建任务列表
    matrix = QUICK_TEST_MATRIX if args.quick else DEFAULT_TEST_MATRIX
    eng_filter  = set(args.engines.split(","))   if args.engines   else None
    strat_filter= set(args.strategies.split(","))if args.strategies else None

    all_tasks: list[tuple[str, list[str]]] = []
    for group in matrix:
        for eid in group["engines"]:
            if eng_filter  and eid not in eng_filter:  continue
            if eid not in valid_engs:
                print(f"  [跳过] 引擎未注册: {eid}")
                continue
            for combo in group["strategies"]:
                valid = [s for s in combo if s in valid_strats]
                if strat_filter:
                    valid = [s for s in valid if s in strat_filter]
                if valid:
                    all_tasks.append((eid, valid))

    # 断点续跑
    ckpt = load_checkpoint() if args.resume else {"completed": [], "results": []}
    prior_results: list  = ckpt["results"]
    prior_completed: list = ckpt["completed"]

    if args.resume and prior_completed:
        print(f"[续跑] 已完成 {len(prior_completed)} 次，继续剩余任务")

    # 过滤已完成任务
    pending = [
        (e, s) for e, s in all_tasks
        if f"{e}|{'+'.join(s)}" not in prior_completed
    ]

    # shuffle + limit
    if args.shuffle:
        random.shuffle(pending)
    if args.limit:
        pending = pending[:args.limit]

    print(f"[计划] {len(pending)} 次回测（共 {len(all_tasks)} 个组合）")
    if not pending:
        print("[完成] 没有待执行任务")
        return

    # 按 workers 切片
    slices: list[list] = [[] for _ in range(args.workers)]
    for i, task in enumerate(pending):
        slices[i % args.workers].append(task)

    results: list   = list(prior_results)
    completed: list = list(prior_completed)
    lock = asyncio.Lock()
    global_start = time.time()

    # 启动 worker 协程（并发）
    worker_tasks = [
        asyncio.create_task(
            worker_loop(i, ports[i], slices[i], args, results, completed, lock, global_start)
        )
        for i in range(args.workers)
    ]

    try:
        if args.timeout_total:
            await asyncio.wait_for(
                asyncio.gather(*worker_tasks),
                timeout=args.timeout_total * 60,
            )
        else:
            await asyncio.gather(*worker_tasks)
    except asyncio.TimeoutError:
        print(f"\n[超时] 已达全局时间限制 {args.timeout_total} 分钟，停止")
        for t in worker_tasks:
            t.cancel()

    # 导出报告
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path("backtest_results") / ts
    export_report(results, out)

    elapsed = time.time() - global_start
    print(f"[完成] 总耗时 {elapsed/60:.1f} 分钟")


# ─── CLI ─────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Crypto Quant Terminal 批量回测（并发版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python batch_backtest.py --quick --limit 5
  python batch_backtest.py --workers 3 --ports 8012,8013,8014
  python batch_backtest.py --since 2022-01-01 --timeout-total 60
  python batch_backtest.py --resume --shuffle
        """,
    )
    p.add_argument("--quick",           action="store_true",      help="快速矩阵（3策略×1引擎）")
    p.add_argument("--workers",         type=int, default=1,       help="并发 worker 数（每个需独立后端）")
    p.add_argument("--ports",           default=None,              help="逗号分隔端口列表（默认 8012, 8013...）")
    p.add_argument("--limit",           type=int, default=None,    help="最多跑 N 个组合")
    p.add_argument("--shuffle",         action="store_true",       help="随机打乱测试顺序")
    p.add_argument("--timeout-total",   type=float, default=None,  help="全局时间限制（分钟）", dest="timeout_total")
    p.add_argument("--resume",          action="store_true",       help="从上次断点续跑")
    p.add_argument("--symbol",          default="BTC/USDT",        help="交易对")
    p.add_argument("--timeframe",       default="1d",              help="时间框架 1d/4h/1h/30m")
    p.add_argument("--since",           default="2022-01-01",      help="起始日期")
    p.add_argument("--until",           default=None,              help="截止日期")
    p.add_argument("--oos-split",       type=float, default=20.0,  dest="oos_split")
    p.add_argument("--optuna-trials",   type=int,   default=80,    dest="optuna_trials")
    p.add_argument("--wfv-folds",       type=int,   default=5,     dest="wfv_folds")
    p.add_argument("--timeout",         type=float, default=600.0, help="单次回测超时（秒）")
    p.add_argument("--engines",         default=None,              help="逗号分隔引擎 ID")
    p.add_argument("--strategies",      default=None,              help="逗号分隔策略 ID")
    p.add_argument("--skip-fetch",      action="store_true",       dest="skip_fetch", help="跳过数据拉取")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
