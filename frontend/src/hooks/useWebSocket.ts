import { useState, useEffect, useRef, useCallback } from 'react';
import type { LogMessage, EngineResultData, RunStatus } from '../types';

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [results, setResults] = useState<EngineResultData[]>([]);
  const [progressPlots, setProgressPlots] = useState<{ step: number; reward: number; entropy: number }[]>([]);
  const [runStatus, setRunStatus] = useState<RunStatus>('idle');
  const [factorWeights, setFactorWeights] = useState<Record<string, number> | null>(null);
  const [degradationWarnings, setDegradationWarnings] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://${window.location.host}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      if (wsRef.current === ws) setConnected(true);
    };

    ws.onmessage = (event) => {
      if (wsRef.current !== ws) return;
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'log' || msg.type === 'info' || msg.type === 'error') {
          const logEntry: LogMessage = {
            type: 'log',
            level: msg.type === 'log' ? (msg.level ?? 'info') : msg.type,
            message: msg.data ?? msg.message ?? '',
            timestamp: new Date().toISOString(),
          };
          setLogs(prev => [...prev.slice(-200), logEntry]);

        } else if (msg.type === 'result') {
          setResults(prev => [...prev, msg.data]);
          setProgressPlots([]);

        } else if (msg.type === 'progress_plot') {
          setProgressPlots(prev => [...prev.slice(-500), msg.data]);

        } else if (msg.type === 'run_status') {
          // 显式状态消息（替代脆弱的字符串匹配）
          setRunStatus(msg.status as RunStatus);
          if (msg.status === 'complete' || msg.status === 'error') {
            setTimeout(() => setProgressPlots([]), 1500);
          }

        } else if (msg.type === 'factor_weights') {
          setFactorWeights(msg.data);

        } else if (msg.type === 'degradation_warning') {
          setDegradationWarnings(msg.strategies as string[]);
        }

      } catch (err) {
        console.error('WS parse error', err);
      }
    };

    ws.onclose = () => {
      if (wsRef.current === ws) {
        setConnected(false);
        setRunStatus('error');
      }
    };

    return () => {
      if (wsRef.current === ws) wsRef.current = null;
      ws.close();
    };
  }, []);

  const clearLogs = useCallback(() => setLogs([]), []);
  const clearResults = useCallback(() => {
    setResults([]);
    setProgressPlots([]);
    setFactorWeights(null);
    setRunStatus('idle');
    setDegradationWarnings([]);
  }, []);

  return { connected, logs, results, progressPlots, runStatus, factorWeights, degradationWarnings, clearLogs, clearResults };
}
