import { useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import ControlPanel from '../components/ControlPanel';
import PerformanceArena from '../components/PerformanceArena';
import Singularity from '../components/Singularity';
import HistoryPanel from '../components/HistoryPanel';
import TabBar from '../components/ui/TabBar';

const MAIN_TABS = [
  { id: 'results',  label: 'RESULTS'  },
  { id: 'history',  label: 'HISTORY'  },
  { id: 'logs',     label: 'LOGS'     },
];

export default function Dashboard() {
  const {
    connected, logs, results, progressPlots,
    runStatus, factorWeights, clearLogs, clearResults,
  } = useWebSocket();

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mainTab, setMainTab]         = useState('results');

  const singularityStatus: 'idle' | 'running' | 'done' | 'error' =
    !connected          ? 'error'   :
    runStatus === 'running'  ? 'running' :
    runStatus === 'complete' ? 'done'    :
    runStatus === 'error'    ? 'error'   : 'idle';

  const recentLog = logs.length > 0 ? logs[logs.length - 1].message : undefined;

  return (
    <div className="w-full min-h-screen bg-bg-primary flex flex-col">
      {/* ── Header ── */}
      <header className="border-b border-border-base px-4 py-1 flex items-center justify-between shrink-0">
        <Singularity status={singularityStatus} recentLog={recentLog} />
        <div className="flex items-center gap-3">
          <span className={`text-caption uppercase tracking-widest ${connected ? 'text-accent-emerald' : 'text-accent-magenta'}`}>
            {connected ? '● LINKED' : '○ OFFLINE'}
          </span>
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
        {sidebarOpen && (
          <aside className="w-[320px] shrink-0 border-r border-border-base overflow-y-auto p-4 flex flex-col gap-4">
            <h2 className="text-heading uppercase tracking-widest border-b border-border-base pb-2">
              TERMINAL CONSOLE
            </h2>
            <ControlPanel connected={connected} runStatus={runStatus} />
          </aside>
        )}

        {/* Main area */}
        <main className="flex-1 min-w-0 flex flex-col p-4 gap-4 overflow-y-auto">
          <TabBar tabs={MAIN_TABS} active={mainTab} onChange={setMainTab} />

          {mainTab === 'results' && (
            <PerformanceArena
              results={results}
              onClear={clearResults}
              progressPlots={progressPlots}
              runStatus={runStatus}
              factorWeights={factorWeights}
            />
          )}

          {mainTab === 'history' && <HistoryPanel />}

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
