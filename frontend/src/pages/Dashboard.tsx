import { useState, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import ControlPanel from '../components/ControlPanel';
import PerformanceArena from '../components/PerformanceArena';
import Singularity from '../components/Singularity';
import HistoryPanel from '../components/HistoryPanel';
import TabBar from '../components/ui/TabBar';
import HelpModal from '../components/ui/HelpModal';
import type { EngineResultData } from '../types';

const MAIN_TABS = [
  { id: 'results',  label: 'RESULTS'  },
  { id: 'history',  label: 'HISTORY'  },
  { id: 'logs',     label: 'LOGS'     },
];

export default function Dashboard() {
  const {
    connected, logs, results, progressPlots,
    runStatus, factorWeights, degradationWarnings, clearLogs, clearResults,
  } = useWebSocket();

  const [sidebarOpen, setSidebarOpen]       = useState(true);
  const [mainTab, setMainTab]               = useState('results');
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [showHelp, setShowHelp]             = useState(false);
  const [comparedResults, setComparedResults] = useState<EngineResultData[]>([]);

  // 引擎跑完自动刷新历史记录
  useEffect(() => {
    if (runStatus === 'complete') {
      setHistoryRefreshKey(k => k + 1);
    }
  }, [runStatus]);

  const handleHistoryCompare = (loaded: EngineResultData[]) => {
    setComparedResults(loaded);
    setMainTab('results');
  };

  const handleClearAll = () => {
    clearResults();
    setComparedResults([]);
  };

  const singularityStatus: 'idle' | 'running' | 'done' | 'error' =
    !connected          ? 'error'   :
    runStatus === 'running'  ? 'running' :
    runStatus === 'complete' ? 'done'    :
    runStatus === 'error'    ? 'error'   : 'idle';

  const recentLog = logs.length > 0 ? logs[logs.length - 1].message : undefined;

  return (
    <div className="w-full min-h-screen bg-bg-primary flex flex-col">
      {showHelp && <HelpModal onClose={() => setShowHelp(false)} />}
      {/* ── Header ── */}
      <header className="border-b border-border-base px-4 py-1 flex items-center justify-between shrink-0">
        <Singularity status={singularityStatus} recentLog={recentLog} />
        <div className="flex items-center gap-3">
          <span className={`text-caption uppercase tracking-widest ${connected ? 'text-accent-emerald' : 'text-accent-magenta'}`}>
            {connected ? '● LINKED' : '○ OFFLINE'}
          </span>
          <button
            onClick={() => setShowHelp(true)}
            className="text-caption text-accent-cyan hover:text-text-primary border border-accent-cyan/40 px-2 py-1 transition-colors"
          >
            [? 新手指南]
          </button>
          <button
            onClick={() => setSidebarOpen(o => !o)}
            className="text-caption text-text-muted hover:text-text-secondary border border-border-dim px-2 py-1 transition-colors"
          >
            {sidebarOpen ? '[◀ HIDE]' : '[▶ CONSOLE]'}
          </button>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* Sidebar — ControlPanel */}
        <aside className={`w-[320px] shrink-0 border-r border-border-base overflow-y-auto p-4 flex flex-col gap-4 ${sidebarOpen ? '' : 'hidden'}`}>
          <h2 className="text-heading uppercase tracking-widest border-b border-border-base pb-2">
            TERMINAL CONSOLE
          </h2>
          <ControlPanel connected={connected} runStatus={runStatus} />
        </aside>

        {/* Main area */}
        <main className="flex-1 min-w-0 flex flex-col p-4 gap-4 overflow-y-auto">
          {/* 降级策略警告 banner */}
          {degradationWarnings.length > 0 && (
            <div className="border border-accent-amber/60 bg-accent-amber/5 p-3 flex flex-col gap-1">
              <div className="text-caption text-accent-amber uppercase tracking-widest mb-1">
                [!] STRATEGY DEGRADATION NOTICE
              </div>
              {degradationWarnings.map((w, i) => (
                <div key={i} className="text-caption text-text-secondary font-mono">&gt; {w}</div>
              ))}
            </div>
          )}

          <TabBar tabs={MAIN_TABS} active={mainTab} onChange={setMainTab} />

          {/* 新手引导横幅 — 仅在 idle 且无结果时显示 */}
          {results.length === 0 && runStatus === 'idle' && (
            <div className="border border-accent-cyan/30 bg-accent-cyan/5 p-3 flex gap-6 text-caption">
              {[
                { step: '① 选数据', desc: '侧边栏 DATA SOURCE 选择数据来源' },
                { step: '② 运行引擎', desc: '展开 ENGINE A（推荐），点击运行' },
                { step: '③ 查看结果', desc: '完成后在此 RESULTS 页查看指标' },
              ].map(item => (
                <div key={item.step} className="flex gap-2">
                  <span className="text-accent-amber font-mono shrink-0">{item.step}</span>
                  <span className="text-text-muted">{item.desc}</span>
                </div>
              ))}
            </div>
          )}

          {mainTab === 'results' && (
            <PerformanceArena
              results={[...results, ...comparedResults]}
              onClear={handleClearAll}
              progressPlots={progressPlots}
              runStatus={runStatus}
              factorWeights={factorWeights}
            />
          )}

          {mainTab === 'history' && (
            <HistoryPanel
              refreshKey={historyRefreshKey}
              onCompare={handleHistoryCompare}
            />
          )}

          {mainTab === 'logs' && (
            <div className="border border-border-base bg-bg-secondary p-4 overflow-y-auto flex-1">
              <div className="flex justify-between items-center mb-3 border-b border-border-dim pb-2">
                <span className="text-heading uppercase tracking-widest">Raw Session Logs</span>
                <button
                  onClick={clearLogs}
                  className="text-caption text-text-secondary hover:text-text-primary transition-colors"
                >
                  [CLEAR]
                </button>
              </div>
              <div className="font-mono text-caption text-text-primary space-y-1">
                {logs.length === 0 && (
                  <div className="text-text-muted">
                    {connected
                      ? '> [SYS] CONNECTION SECURED. WAITING FOR INSTRUCTIONS...'
                      : '> [ERR] AWAITING WEBSOCKET LINK...'}
                  </div>
                )}
                {logs.map((log, i) => (
                  <div key={i} className={log.level === 'error' ? 'text-accent-magenta' : ''}>
                    <span className="text-text-muted">
                      [{log.timestamp
                        ? new Date(log.timestamp).toISOString().split('T')[1].slice(0, 8)
                        : '??:??:??'}]
                    </span>{' '}
                    {log.message}
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
