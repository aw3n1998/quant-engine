// frontend/src/services/api.ts

import type { StrategyInfo, EngineInfo, RunRequest } from "../types";

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

export async function uploadData(file: File): Promise<{ status: string; rows: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE_URL}/upload-data`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload Error ${res.status}: ${text}`);
  }
  return res.json();
}
