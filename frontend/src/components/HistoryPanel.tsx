import React, { useEffect, useState, useMemo } from 'react';
import Plot from 'react-plotly.js';
import { fetchHistory, fetchHistoryRun, deleteHistoryRun, validateParams, combineEngines } from '../services/api';
import type { RunHistoryItem, EngineResultData } from '../types';

interface Props {
  refreshKey?: number;
  onCompare?: (results: EngineResultData[]) => void;
}

type HistoryRow =
  | { type: 'single'; data: RunHistoryItem }
  | { type: 'batch'; batch_id: string; runs: RunHistoryItem[] };

export default function HistoryPanel({ refreshKey = 0, onCompare }: Props) {
  const [history, setHistory]         = useState<RunHistoryItem[]>([]);
  const [expanded, setExpanded]       = useState<string | null>(null);
  const [expandedData, setExpandedData] = useState<Record<string, unknown> | null>(null);
  const [expandedBatches, setExpandedBatches] = useState<Set<string>>(new Set());
  const [loading, setLoading]         = useState(false);

  // 多选状态
  const [selected, setSelected]       = useState<Set<string>>(new Set());
  // 融合权重 { run_id: weight }
  const [fuseWeights, setFuseWeights] = useState<Record<string, number>>({});
  const [showFusePanel, setShowFusePanel] = useState(false);
  const [fuseLabel, setFuseLabel]     = useState('Engine Fusion');

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const load = async () => {
    try {
      const data = await fetchHistory(100);
      setHistory(data);
      setCurrentPage(1);
    } catch { /* silently ignore */ }
  };

  useEffect(() => { load(); }, [refreshKey]);

  // Compute grouped history
  const groupedHistory = useMemo<HistoryRow[]>(() => {
    const groups: Record<string, RunHistoryItem[]> = {};
    const rows: HistoryRow[] = [];

    for (const item of history) {
      if (item.batch_id) {
        if (!groups[item.batch_id]) {
          groups[item.batch_id] = [];
          rows.push({ type: 'batch', batch_id: item.batch_id, runs: groups[item.batch_id] });
        }
        groups[item.batch_id].push(item);
      } else {
        rows.push({ type: 'single', data: item });
      }
    }

    return rows.map(row => {
      // If a batch group somehow only has 1 item, render it as single
      if (row.type === 'batch' && row.runs.length === 1) {
        return { type: 'single', data: row.runs[0] };
      }
      return row;
    });
  }, [history]);

  // 计算当前页数据
  const totalPages = Math.ceil(groupedHistory.length / itemsPerPage);
  const currentData = groupedHistory.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  // 初始化融合权重（每次选中变化时均匀分配）
  useEffect(() => {
    const ids = [...selected];
    const eq = 1 / Math.max(ids.length, 1);
    setFuseWeights(Object.fromEntries(ids.map(id => [id, eq])));
  }, [selected]);

  const toggleSelect = (run_id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelected(prev => {
      const next = new Set(prev);
      next.has(run_id) ? next.delete(run_id) : next.add(run_id);
      return next;
    });
  };

  const toggleBatch = (batch_id: string) => {
    setExpandedBatches(prev => {
      const next = new Set(prev);
      if (next.has(batch_id)) next.delete(batch_id);
      else next.add(batch_id);
      return next;
    });
  };

  const handleExpand = async (run_id: string) => {
    if (expanded === run_id) { setExpanded(null); setExpandedData(null); return; }
    setLoading(true);
    try {
      const data = await fetchHistoryRun(run_id);
      setExpanded(run_id);
      setExpandedData(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleDelete = async (run_id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteHistoryRun(run_id);
    setHistory(prev => prev.filter(r => r.run_id !== run_id));
    setSelected(prev => { const next = new Set(prev); next.delete(run_id); return next; });
    if (expanded === run_id) { setExpanded(null); setExpandedData(null); }
  };

  const handleValidate = async (run_id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setLoading(true);
      await validateParams(run_id);
      setTimeout(() => { load(); setLoading(false); }, 500);
    } catch (err) { console.error('OOS 验证失败:', err); setLoading(false); }
  };

  // ── 多选对比 ──────────────────────────────────────────────────────
  const handleCompare = async () => {
    if (selected.size < 2 || !onCompare) return;
    setLoading(true);
    try {
      const loaded: EngineResultData[] = [];
      for (const run_id of selected) {
        const data = await fetchHistoryRun(run_id) as any;
        loaded.push({
          engine:        data.engine       ?? '?',
          strategy:      (data.strategies  ?? []).join('+'),
          strategy_name: `[历史] ${data.engine}/${(data.strategies??[]).slice(0,2).join('+')}`,
          best_params:   data.best_params  ?? {},
          sharpe:        data.sharpe       ?? 0,
          calmar:        data.calmar       ?? 0,
          max_drawdown:  data.max_drawdown ?? 0,
          annual_return: data.annual_return ?? 0,
          equity_curve:  data.equity_curve ?? [],
          weight_history: data.weight_history ?? [],
          strategy_names: data.strategies ?? [],
        });
      }
      onCompare(loaded);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  // ── 引擎融合 ──────────────────────────────────────────────────────
  const handleFuse = async () => {
    const ids = [...selected];
    // 归一化权重
    const raw = ids.map(id => fuseWeights[id] ?? 1);
    const total = raw.reduce((a, b) => a + b, 0);
    const norm = raw.map(w => w / total);

    try {
      setLoading(true);
      setShowFusePanel(false);
      await combineEngines({
        run_ids: ids,
        weights: norm,
        label: fuseLabel,
      });
      // 结果通过 WebSocket 返回，自动显示在 PerformanceArena
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const renderRunRow = (row: RunHistoryItem, isChild = false) => (
    <React.Fragment key={row.run_id}>
      <tr
        className={`border-b border-[#008F11]/10 cursor-pointer transition-colors ${
          selected.has(row.run_id)
            ? 'bg-[#00FFFF]/5 border-[#00FFFF]/20'
            : 'hover:bg-[#008F11]/10'
        }`}
        onClick={() => handleExpand(row.run_id)}
      >
        <td className={`py-1 pr-2 ${isChild ? 'pl-4' : ''}`}>
          <input
            type="checkbox"
            className="accent-[#00FFFF]"
            checked={selected.has(row.run_id)}
            onClick={e => toggleSelect(row.run_id, e)}
            onChange={() => {}}
          />
        </td>
        <td className="py-1 pr-4 text-[#008F11]">
          {new Date(row.timestamp).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
        </td>
        <td className="py-1 pr-4 text-[#00FFFF]">
          {isChild && <span className="text-[#008F11] mr-1 opacity-70">└─</span>}
          {row.engine}
        </td>
        <td className="py-1 pr-4 text-[#008F11] max-w-[120px] truncate">{row.data_source}</td>
        <td className={`py-1 pr-4 text-right font-bold ${row.calmar > 0 ? 'text-[#00FF41]' : 'text-[#C724FF]'}`}>
          {row.calmar?.toFixed(2) ?? '-'}
        </td>
        <td className={`py-1 pr-4 text-right ${(row.annual_return ?? 0) > 0 ? 'text-[#00FF41]' : 'text-[#C724FF]'}`}>
          {row.annual_return != null ? `${(row.annual_return * 100).toFixed(1)}%` : '-'}
        </td>
        <td className="py-1 pr-4 text-right text-[#00FFFF]">
          {row.sharpe?.toFixed(2) ?? '-'}
        </td>
        <td className="py-1 flex items-center gap-1">
          {row.engine !== 'drl' && (
            <button
              onClick={e => handleValidate(row.run_id, e)}
              title="用当前已加载数据验证此run的参数（样本外验证）"
              className="text-[10px] px-1 border border-[#00FFFF]/50 text-[#00FFFF]/70 hover:border-[#00FFFF] hover:text-[#00FFFF] transition-colors"
            >OOS</button>
          )}
          <button
            onClick={e => handleDelete(row.run_id, e)}
            className="text-[#C724FF]/50 hover:text-[#C724FF] px-1"
          >✕</button>
        </td>
      </tr>

      {expanded === row.run_id && expandedData && (
        <tr key={`${row.run_id}-exp`}>
          <td colSpan={8} className="pb-4 pt-2">
            {Array.isArray((expandedData as any).equity_curve) && (expandedData as any).equity_curve.length > 0 && (
              <div className="border border-[#008F11]/30 h-[200px]">
                <Plot
                  data={[{
                    y: (expandedData as any).equity_curve,
                    type: 'scatter', mode: 'lines', fill: 'tozeroy', name: 'OOS Equity',
                    line: { color: '#00FF41', width: 1 },
                    fillcolor: 'rgba(0,255,65,0.08)',
                  }]}
                  layout={{
                    title: `[历史] ${row.engine} | ${row.data_source}`,
                    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                    font: { color: '#00FF41', size: 10 },
                    margin: { l: 40, r: 10, t: 30, b: 30 },
                    xaxis: { gridcolor: '#008F11', gridwidth: 0.5 },
                    yaxis: { gridcolor: '#008F11', gridwidth: 0.5 },
                  } as any}
                  useResizeHandler style={{ width: '100%', height: '100%' }}
                />
              </div>
            )}
          </td>
        </tr>
      )}
    </React.Fragment>
  );

  if (history.length === 0) return null;

  const selectedArr = [...selected];
  const selectedRows = history.filter(r => selected.has(r.run_id));

  return (
    <div className="border border-[#008F11]/50 bg-[#050a05] p-4 rounded">
      {/* Header */}
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-sm uppercase text-[#00FFFF]">[历史运行记录]</h3>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <span className="text-xs text-[#C724FF] font-mono">
              已选 {selected.size} 条
            </span>
          )}
          <button onClick={load} className="text-xs text-[#008F11] hover:text-[#00FF41]">[刷新]</button>
        </div>
      </div>

      {/* 多选操作栏 */}
      {selected.size >= 2 && (
        <div className="mb-3 border border-[#00FFFF]/30 bg-[#00FFFF]/5 p-2 flex flex-wrap gap-2 items-center">
          <span className="text-[10px] text-[#00FFFF] font-mono uppercase tracking-widest">
            已选 {selected.size} 条 →
          </span>
          {onCompare && (
            <button
              onClick={handleCompare}
              disabled={loading}
              className="text-[11px] px-2 py-0.5 border border-[#00FFFF] text-[#00FFFF] hover:bg-[#00FFFF]/10 transition-colors font-mono disabled:opacity-50"
            >
              [对比曲线 COMPARE]
            </button>
          )}
          <button
            onClick={() => setShowFusePanel(v => !v)}
            className="text-[11px] px-2 py-0.5 border border-[#C724FF] text-[#C724FF] hover:bg-[#C724FF]/10 transition-colors font-mono"
          >
            [融合引擎 FUSE]
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-[11px] px-2 py-0.5 border border-[#008F11]/50 text-[#008F11] hover:text-[#00FF41] transition-colors font-mono ml-auto"
          >
            [清除选择]
          </button>
        </div>
      )}

      {/* 融合配置面板 */}
      {showFusePanel && selected.size >= 2 && (
        <div className="mb-3 border border-[#C724FF]/40 bg-[#C724FF]/5 p-3 flex flex-col gap-2">
          <div className="text-[10px] text-[#C724FF] uppercase tracking-widest mb-1">
            [引擎融合配置] — 调整权重后点击 FUSE
          </div>
          <div className="flex flex-col gap-2">
            {selectedRows.map(row => (
              <div key={row.run_id} className="flex items-center gap-2 text-[11px] font-mono">
                <span className="text-[#008F11] w-32 truncate">
                  [{row.engine}] {row.data_source}
                </span>
                <input
                  type="range" min={0} max={100}
                  value={Math.round((fuseWeights[row.run_id] ?? 0.5) * 100)}
                  onChange={e => {
                    const v = Number(e.target.value) / 100;
                    setFuseWeights(prev => ({ ...prev, [row.run_id]: v }));
                  }}
                  className="flex-1 accent-[#C724FF]"
                />
                <span className="text-[#C724FF] w-10 text-right">
                  {Math.round((fuseWeights[row.run_id] ?? 0.5) * 100)}%
                </span>
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-1">
            <input
              value={fuseLabel}
              onChange={e => setFuseLabel(e.target.value)}
              className="flex-1 bg-transparent border border-[#C724FF]/40 text-[#C724FF] text-[11px] font-mono px-2 py-0.5 outline-none"
              placeholder="融合结果名称..."
            />
            <button
              onClick={handleFuse}
              disabled={loading}
              className="text-[11px] px-3 py-0.5 border border-[#C724FF] text-[#C724FF] bg-[#C724FF]/10 hover:bg-[#C724FF]/20 transition-colors font-mono disabled:opacity-50"
            >
              {loading ? '融合中...' : '[FUSE NOW]'}
            </button>
          </div>
        </div>
      )}

      {/* History Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-[#008F11]/30 text-[#008F11]">
              <th className="pb-1 pr-2 w-4">
                <input
                  type="checkbox"
                  className="accent-[#00FFFF]"
                  checked={selected.size === history.length && history.length > 0}
                  onChange={e => {
                    if (e.target.checked) setSelected(new Set(history.map(r => r.run_id)));
                    else setSelected(new Set());
                  }}
                />
              </th>
              <th className="text-left pb-1 pr-4">时间</th>
              <th className="text-left pb-1 pr-4">引擎</th>
              <th className="text-left pb-1 pr-4">数据</th>
              <th className="text-right pb-1 pr-4">Calmar</th>
              <th className="text-right pb-1 pr-4">年化</th>
              <th className="text-right pb-1 pr-4">Sharpe</th>
              <th className="pb-1"></th>
            </tr>
          </thead>
          <tbody>
            {currentData.map((group, i) => {
              if (group.type === 'single') {
                return renderRunRow(group.data, false);
              } else {
                const isExpanded = expandedBatches.has(group.batch_id);
                return (
                  <React.Fragment key={group.batch_id}>
                    <tr
                      className="border-b border-[#C724FF]/30 bg-[#C724FF]/5 cursor-pointer hover:bg-[#C724FF]/10 transition-colors"
                      onClick={() => toggleBatch(group.batch_id)}
                    >
                      <td colSpan={8} className="py-1.5 px-2 text-[#C724FF] font-bold">
                        <span className="mr-2 inline-block w-3 text-center">
                          {isExpanded ? '▼' : '▶'}
                        </span>
                        Batch Test Group ({group.runs.length} runs)
                        <span className="ml-4 text-[10px] text-[#C724FF]/70 font-normal">
                          ID: {group.batch_id.slice(0, 8)}...
                        </span>
                      </td>
                    </tr>
                    {isExpanded && group.runs.map(run => renderRunRow(run, true))}
                  </React.Fragment>
                );
              }
            })}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-4 mt-3">
          <button
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            className="text-[#00FFFF] border border-[#00FFFF] px-2 py-0.5 text-xs hover:bg-[#00FFFF]/20 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            &larr; PREV
          </button>
          <span className="text-[#008F11] text-xs font-mono">
            PAGE {currentPage} / {totalPages}
          </span>
          <button
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            className="text-[#00FFFF] border border-[#00FFFF] px-2 py-0.5 text-xs hover:bg-[#00FFFF]/20 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            NEXT &rarr;
          </button>
        </div>
      )}

      {loading && <div className="text-xs text-[#008F11] mt-2 animate-pulse">Loading...</div>}
    </div>
  );
}
