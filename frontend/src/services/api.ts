// frontend/src/services/api.ts

import type { StrategyInfo, EngineInfo, RunRequest, RunHistoryItem } from "../types";

const BASE_URL = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API Error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function fetchStrategies(): Promise<StrategyInfo[]> {
  return request<StrategyInfo[]>("/strategies");
}

export async function fetchEngines(): Promise<EngineInfo[]> {
  return request<EngineInfo[]>("/engines");
}

export async function fetchConfig(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/config");
}

export async function runEngine(payload: RunRequest): Promise<{ status: string }> {
  return request<{ status: string }>("/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadData(file: File, timeframe: string = "1d"): Promise<{ status: string; rows: string; timeframe: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE_URL}/upload-data?timeframe=${encodeURIComponent(timeframe)}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload Error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function fetchBinance(payload: {
  symbol: string;
  timeframe: string;
  limit: number;
  use_mev?: boolean;
  use_nlp?: boolean;
  worldnews_api_key?: string;
}): Promise<{
  status: string;
  rows: number;
  symbol: string;
  timeframe: string;
  date_range: string;
  mev_enabled: boolean;
  nlp_enabled: boolean;
}> {
  return request("/fetch-binance", { method: "POST", body: JSON.stringify(payload) });
}

export async function fetchHistory(limit = 50): Promise<RunHistoryItem[]> {
  return request<RunHistoryItem[]>(`/history?limit=${limit}`);
}

export async function fetchHistoryRun(run_id: string): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/history/${run_id}`);
}

export async function deleteHistoryRun(run_id: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/history/${run_id}`, { method: "DELETE" });
}
