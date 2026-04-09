import { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import { fetchHistory, fetchHistoryRun, deleteHistoryRun, validateParams } from '../services/api';
import type { RunHistoryItem } from '../types';

interface Props {
  refreshKey?: number;
}

export default function HistoryPanel({ refreshKey = 0 }: Props) {
  const [history, setHistory] = useState<RunHistoryItem[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [expandedData, setExpandedData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      const data = await fetchHistory(20);
      setHistory(data);
    } catch (e) {
      // silently ignore if backend not ready
    }
  };

  useEffect(() => {
    load();
  }, [refreshKey]);

  const handleExpand = async (run_id: string) => {
    if (expanded === run_id) {
      setExpanded(null);
      setExpandedData(null);
      return;
    }
    setLoading(true);
    try {
      const data = await fetchHistoryRun(run_id);
      setExpanded(run_id);
      setExpandedData(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (run_id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteHistoryRun(run_id);
    setHistory(prev => prev.filter(r => r.run_id !== run_id));
    if (expanded === run_id) { setExpanded(null); setExpandedData(null); }
  };

  const handleValidate = async (run_id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setLoading(true);
      await validateParams(run_id);
      // 验证完成后刷新历史列表
      setTimeout(() => {
        load();
        setLoading(false);
      }, 500);
    } catch (err) {
      console.error('OOS 验证失败:', err);
      setLoading(false);
    }
  };

  if (history.length === 0) return null;

  return (
    <div className="border border-[#008F11]/50 bg-[#050a05] p-4 rounded">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-sm uppercase text-[#00FFFF]">[历史运行记录]</h3>
        <button onClick={load} className="text-xs text-[#008F11] hover:text-[#00FF41]">[刷新]</button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-[#008F11]/30 text-[#008F11]">
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
            {history.map(row => (
              <>
                <tr
                  key={row.run_id}
                  className="border-b border-[#008F11]/10 cursor-pointer hover:bg-[#008F11]/10 transition-colors"
                  onClick={() => handleExpand(row.run_id)}
                >
                  <td className="py-1 pr-4 text-[#008F11]">
                    {new Date(row.timestamp).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="py-1 pr-4 text-[#00FFFF]">{row.engine}</td>
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
                        onClick={(e) => handleValidate(row.run_id, e)}
                        title="用当前已加载数据验证此run的参数（样本外验证）"
                        className="text-[10px] px-1 border border-[#00FFFF]/50 text-[#00FFFF]/70 hover:border-[#00FFFF] hover:text-[#00FFFF] transition-colors"
                      >OOS</button>
                    )}
                    <button
                      onClick={(e) => handleDelete(row.run_id, e)}
                      className="text-[#C724FF]/50 hover:text-[#C724FF] px-1"
                    >✕</button>
                  </td>
                </tr>
                {expanded === row.run_id && expandedData && (
                  <tr key={`${row.run_id}-expanded`}>
                    <td colSpan={7} className="pb-4 pt-2">
                      {Array.isArray((expandedData as any).equity_curve) && (expandedData as any).equity_curve.length > 0 && (
                        <div className="border border-[#008F11]/30 h-[200px]">
                          <Plot
                            data={[{
                              y: (expandedData as any).equity_curve,
                              type: 'scatter',
                              mode: 'lines',
                              fill: 'tozeroy',
                              line: { color: '#00FF41', width: 1 },
                              fillcolor: 'rgba(0,255,65,0.08)',
                            }]}
                            layout={{
                              title: `[历史] ${row.engine} | ${row.data_source}`,
                              paper_bgcolor: 'transparent',
                              plot_bgcolor: 'transparent',
                              font: { color: '#00FF41', size: 10 },
                              margin: { l: 40, r: 10, t: 30, b: 30 },
                              xaxis: { gridcolor: '#008F11', gridwidth: 0.5 },
                              yaxis: { gridcolor: '#008F11', gridwidth: 0.5 },
                            } as any}
                            useResizeHandler
                            style={{ width: '100%', height: '100%' }}
                          />
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
      {loading && <div className="text-xs text-[#008F11] mt-2">Loading...</div>}
    </div>
  );
}
