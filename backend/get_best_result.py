import sqlite3
import json
from datetime import datetime, timedelta

conn = sqlite3.connect('data/quant_engine.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get results from the last 2 hours (UTC)
two_hours_ago = (datetime.utcnow() - timedelta(hours=2)).isoformat()
cursor.execute('''
    SELECT engine, strategies, timeframe, sharpe, calmar, max_drawdown, annual_return, timestamp 
    FROM run_history 
    WHERE timestamp > ? AND sharpe IS NOT NULL
    ORDER BY sharpe DESC LIMIT 5
''', (two_hours_ago,))

rows = [dict(r) for r in cursor.fetchall()]

if rows:
    best = rows[0]
    print(f"--- 最佳回测结果 (最近 2 小时) ---")
    print(f"引擎: {best['engine']}")
    print(f"策略组合: {best['strategies']}")
    print(f"时间框架: {best['timeframe']}")
    print(f"夏普比率 (Sharpe): {best['sharpe']:.4f}")
    print(f"卡玛比率 (Calmar): {best['calmar']:.4f}")
    print(f"年化收益率 (Return): {best['annual_return']*100:.2f}%")
    print(f"最大回撤 (MaxDD): {best['max_drawdown']*100:.2f}%")
    print(f"运行时间: {best['timestamp']}")
else:
    print("最近 2 小时内没有有效的回测记录。")
