import sqlite3
import json

conn = sqlite3.connect('data/quant_engine.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get the latest 10 results
cursor.execute('''
    SELECT engine, strategies, timeframe, sharpe, calmar, max_drawdown, annual_return, timestamp 
    FROM run_history 
    ORDER BY timestamp DESC LIMIT 10
''')

rows = [dict(r) for r in cursor.fetchall()]
print(json.dumps(rows, indent=2, ensure_ascii=False))
