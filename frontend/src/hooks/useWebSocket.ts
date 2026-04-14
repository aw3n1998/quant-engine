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
  
  const [batchProgress, setBatchProgress] = useState<string>('');
  const [batchResults, setBatchResults] = useState<EngineResultData[]>([]);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`ws://${window.location.host}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      reconnectAttempts.current = 0; // Reset attempts on successful connection
      
      // Start heartbeat
      if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30000); // 30s heartbeat
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        // Ignore pong messages from heartbeat
        if (msg.type === 'pong') return;

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
          setRunStatus(msg.status as RunStatus);
          if (msg.status === 'complete' || msg.status === 'error') {
            setTimeout(() => setProgressPlots([]), 1500);
          }

        } else if (msg.type === 'factor_weights') {
          setFactorWeights(msg.data);

        } else if (msg.type === 'degradation_warning') {
          setDegradationWarnings(msg.strategies as string[]);
        } else if (msg.type === 'batch_progress') {
          setBatchProgress(`[${msg.progress}] ${msg.message}`);
        } else if (msg.type === 'batch_summary') {
          setBatchResults(prev => [...prev, msg.data]);
        }

      } catch (err) {
        console.error('WS parse error', err);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (runStatus === 'running') setRunStatus('error');
      
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
      }

      // Reconnection logic with exponential backoff (max 5 minutes)
      const attempts = reconnectAttempts.current;
      const delay = Math.min(1000 * Math.pow(2, attempts), 300000);
      reconnectAttempts.current += 1;
      
      console.log(`WebSocket disconnected. Reconnecting in ${delay}ms...`);
      reconnectTimeoutRef.current = setTimeout(connect, delay);
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      ws.close(); // Trigger onclose for reconnection
    };
  }, [runStatus]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on explicit unmount
        wsRef.current.close();
      }
    };
  }, [connect]);

  const clearLogs = useCallback(() => setLogs([]), []);
  const clearResults = useCallback(() => {
    setResults([]);
    setProgressPlots([]);
    setFactorWeights(null);
    setRunStatus('idle');
    setDegradationWarnings([]);
    setBatchProgress('');
    setBatchResults([]);
  }, []);

  return { 
    connected, logs, results, progressPlots, runStatus, factorWeights, degradationWarnings, 
    batchProgress, batchResults, 
    clearLogs, clearResults 
  };
}
