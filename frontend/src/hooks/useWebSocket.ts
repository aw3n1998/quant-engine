import { useState, useEffect, useRef } from "react";
import type { LogMessage, EngineResultData } from "../types";

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [results, setResults] = useState<EngineResultData[]>([]);
  const [progressPlots, setProgressPlots] = useState<{step: number, reward: number, entropy: number}[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Utilize the Vite proxy configuration mapped to /ws
    const ws = new WebSocket(`ws://${window.location.host}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      if (wsRef.current === ws) {
        setConnected(true);
      }
    };

    ws.onmessage = (event) => {
      if (wsRef.current !== ws) return;
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "log" || msg.type === "info" || msg.type === "error") {
          const logEntry: LogMessage = {
            type: "log",
            level: msg.type === "log" ? "info" : msg.type,
            message: msg.data,
            timestamp: new Date().toISOString(),
          };
          setLogs((prev) => [...prev.slice(-200), logEntry]);
        } else if (msg.type === "result") {
          setResults((prev) => [...prev, msg.data]);
        } else if (msg.type === "progress_plot") {
          setProgressPlots((prev) => [...prev, msg.data]);
        }
      } catch (err) {
        console.error("Failed to parse WS message", err);
      }
    };

    ws.onclose = () => {
      if (wsRef.current === ws) {
        setConnected(false);
      }
    };

    return () => {
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
      ws.close();
    };
  }, []);

  const clearLogs = () => setLogs([]);
  const clearResults = () => {
    setResults([]);
    setProgressPlots([]);
  };

  return { connected, logs, results, progressPlots, clearLogs, clearResults };
}
