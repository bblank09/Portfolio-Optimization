import type { BacktestRequest, BacktestResult, DataStatus, SecFund } from "../types/backtest";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export function assertSecOnly(result: unknown) {
  const data = result as { data_source?: string };
  if (data.data_source && data.data_source !== "sec_open_data") {
    throw new Error("Production app accepts SEC Open Data results only.");
  }
}

function extractErrorMessage(text: string): string {
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      return parsed.detail
        .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : JSON.stringify(item)))
        .join("; ");
    }
  } catch {
    // Not JSON — fall through and use the raw text.
  }
  return text;
}

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
    ...options
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(extractErrorMessage(text) || `Request failed with status ${response.status}`);
  }
  const data = (await response.json()) as T;
  assertSecOnly(data);
  return data;
}

export async function fetchFunds(): Promise<SecFund[]> {
  const payload = await requestJson<{ data_source: "sec_open_data"; funds: SecFund[] }>("/api/funds");
  return payload.funds;
}

export async function fetchDataStatus(): Promise<DataStatus> {
  return requestJson<DataStatus>("/api/data-status");
}

// The longest continuous date range where every given fund has a complete
// monthly NAV observation -- computed server-side with the exact same
// align/completeness logic the backtest engine applies, since a naive
// client-side "latest nav_start .. earliest nav_end" intersection can
// still contain a real gap (e.g. the 2024-06 to 2024-11 SEC-wide
// incident) that the engine would reject.
export async function fetchTestableRange(projIds: string[]): Promise<{ start: string | null; end: string | null }> {
  if (!projIds.length) return { start: null, end: null };
  const params = new URLSearchParams({ proj_ids: projIds.join(",") });
  return requestJson<{ start: string | null; end: string | null }>(`/api/funds/testable-range?${params.toString()}`);
}

export async function fetchBacktestByRunId(runId: string): Promise<BacktestResult> {
  return requestJson<BacktestResult>(`/api/backtests/${encodeURIComponent(runId)}`);
}

export async function runBacktest(payload: BacktestRequest): Promise<BacktestResult> {
  const result = await requestJson<Omit<BacktestResult, "request">>("/api/backtests", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return { ...result, request: payload };
}
