import { useEffect } from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import type { LogMessage, EngineResultData } from "../types";
import ControlPanel from "../components/ControlPanel";
import PerformanceArena from "../components/PerformanceArena";
import Singularity from "../components/Singularity";

export default function Dashboard() {
  const { connected, logs, results, progressPlots, clearLogs, clearResults } = useWebSocket();

  // Calculate status
  const recentLog = logs.length > 0 ? logs[logs.length - 1].message : undefined;
  let status: 'idle' | 'running' | 'done' | 'error' = connected ? 'idle' : 'error';
  
  if (connected && logs.length > 0 && recentLog) {
    const msg = recentLog.toLowerCase();
    
    // Check for explicit completion first to avoid intermediate converging logs breaking the overlay
    if (msg.includes('all strategies completed') || msg.includes('failed') || msg.includes('standby')) {
      status = 'done';
    } else if (msg.includes('start') || msg.includes('running') || msg.includes('optimizing') || msg.includes('evaluating') || msg.includes('training') || msg.includes('ppo') || msg.includes('converging') || msg.includes('forge')) {
      status = 'running';
    } else {
      status = 'idle';
    }
  }

  return (
    <div className="w-full mt-2">
      {/* Magnetic Field Graphic Logo at Top */}
      <header className="mb-8 flex justify-center">
        <Singularity status={status} recentLog={recentLog} />
      </header>

      <div className="flex flex-col md:flex-row gap-8 w-full mt-8">
        {/* Streamlit style Sidebar (left column) */}
        <aside className="w-full md:w-[350px] shrink-0 border-r border-[#008F11] pr-4">
          <h2 className="text-xl border-b border-[#008F11] pb-2 mb-4">TERMINAL CONSOLE</h2>
          <ControlPanel connected={connected} />
        </aside>

      {/* Main Canvas */}
      <section className="flex-1 min-w-0">
        <PerformanceArena results={results} onClear={clearResults} progressPlots={progressPlots} status={status} />
        
        {/* Terminal logs printout at bottom */}
        <div className="mt-8 border border-[#008F11] bg-[#050a05] p-4 rounded max-h-64 overflow-y-auto">
          <h3 className="mb-2 uppercase text-shadow-neon text-sm border-b border-[#008F11]/50 pb-1">Raw Session Logs</h3>
          <div className="font-mono text-xs text-[#00FF41] space-y-1">
            {logs.length === 0 && (
              <div className="opacity-50">
                {connected ? '> [SYS] CONNECTION SECURED. WAITING FOR INSTRUCTIONS...' : '> [ERR] AWAITING WEBSOCKET LINK...'}
              </div>
            )}
            {logs.map((log, i) => (
              <div key={i} className={`opacity-${Math.max(100 - (logs.length - i) * 5, 30)}`}>
                <span className="text-gray-500">[{log.timestamp ? new Date(log.timestamp).toISOString().split('T')[1].slice(0, -1) : ''}]</span> 
                {log.level === 'error' ? <span className="text-[#c724ff] ml-2">ERR:</span> : ''} {log.message}
              </div>
            ))}
          </div>
        </div>
      </section>
      </div>
    </div>
  );
}
