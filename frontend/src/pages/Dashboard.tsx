import { useWebSocket } from "../hooks/useWebSocket";
import ControlPanel from "../components/ControlPanel";
import PerformanceArena from "../components/PerformanceArena";
import Singularity from "../components/Singularity";
import HistoryPanel from "../components/HistoryPanel";

export default function Dashboard() {
  const { connected, logs, results, progressPlots, runStatus, factorWeights, clearLogs, clearResults } =
    useWebSocket();

  // 直接使用后端 run_status 消息，不再依赖脆弱的日志字符串匹配
  const singularityStatus: 'idle' | 'running' | 'done' | 'error' =
    !connected ? 'error' :
    runStatus === 'running' ? 'running' :
    runStatus === 'complete' ? 'done' :
    runStatus === 'error' ? 'error' :
    'idle';

  const recentLog = logs.length > 0 ? logs[logs.length - 1].message : undefined;

  return (
    <div className="w-full mt-2">
      <header className="mb-6 flex justify-center">
        <Singularity status={singularityStatus} recentLog={recentLog} />
      </header>

      <div className="flex flex-col md:flex-row gap-8 w-full">
        <aside className="w-full md:w-[360px] shrink-0 border-r border-[#008F11] pr-4">
          <h2 className="text-xl border-b border-[#008F11] pb-2 mb-4">TERMINAL CONSOLE</h2>
          <ControlPanel connected={connected} runStatus={runStatus} />
        </aside>

        <section className="flex-1 min-w-0">
          <PerformanceArena
            results={results}
            onClear={clearResults}
            progressPlots={progressPlots}
            runStatus={runStatus}
            factorWeights={factorWeights}
          />

          <div className="mt-6">
            <HistoryPanel />
          </div>

          {/* 原始日志 */}
          <div className="mt-4 border border-[#008F11] bg-[#050a05] p-4 rounded max-h-48 overflow-y-auto">
            <h3 className="mb-2 uppercase text-sm border-b border-[#008F11]/50 pb-1 flex justify-between items-center">
              <span>Raw Session Logs</span>
              <button onClick={clearLogs} className="text-[#008F11] hover:text-[#00FF41] text-xs">[CLEAR]</button>
            </h3>
            <div className="font-mono text-xs text-[#00FF41] space-y-1">
              {logs.length === 0 && (
                <div className="opacity-50">
                  {connected
                    ? '> [SYS] CONNECTION SECURED. WAITING FOR INSTRUCTIONS...'
                    : '> [ERR] AWAITING WEBSOCKET LINK...'}
                </div>
              )}
              {logs.map((log, i) => (
                <div key={i} className={log.level === 'error' ? 'text-[#c724ff]' : ''}>
                  <span className="text-gray-600">
                    [{log.timestamp
                      ? new Date(log.timestamp).toISOString().split('T')[1].slice(0, 8)
                      : ''}]
                  </span>{' '}
                  {log.message}
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
