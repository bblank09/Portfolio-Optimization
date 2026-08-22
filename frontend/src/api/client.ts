import type { BacktestRequest, BacktestResult, DataStatus, SecFund } from "../types/backtest";
import type { DataFrequency, OptimizeRequest, OptimizeResult, OptimizeRunResult } from "../types/optimize";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const REQUEST_TIMEOUT_MS = 30_000;
// POST /api/optimize runs a real mean-variance/risk-parity/etc. solve plus,
// when enabled, a rolling-window out-of-sample re-evaluation across many
// folds -- a legitimately CPU-heavy request that has measured 30-100+s
// under load (see the CI investigation in frontend/playwright.config.ts).
// The generic 30s budget above aborts it client-side well before the
// backend can finish, surfacing a false "request timed out" error even
// though the backend goes on to complete the run successfully.
const OPTIMIZE_REQUEST_TIMEOUT_MS = 180_000;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function assertSecOnly(result: unknown) {
  const data = result as { data_source?: string; dataSource?: string };
  const source = data.data_source ?? data.dataSource;
  if (source && source !== "sec_open_data") {
    throw new Error("Production app accepts SEC Open Data results only.");
  }
}

function extractError(text: string): { message: string; code: string | null } {
  try {
    const parsed = JSON.parse(text) as { detail?: unknown; code?: unknown };
    const code = typeof parsed.code === "string" ? parsed.code : null;
    if (typeof parsed.detail === "string") return { message: parsed.detail, code };
    if (Array.isArray(parsed.detail)) {
      return {
        message: parsed.detail
          .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : JSON.stringify(item)))
          .join("; "),
        code
      };
    }
  } catch {
    // Not JSON — fall through and use the raw text.
  }
  return { message: text, code: null };
}

async function requestJson<T>(path: string, options?: RequestInit, timeoutMs: number = REQUEST_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
      ...options,
      signal: controller.signal
    });
    if (!response.ok) {
      const text = await response.text();
      const error = extractError(text);
      throw new ApiError(error.message || `Request failed with status ${response.status}`, response.status, error.code);
    }
    const data = (await response.json()) as T;
    assertSecOnly(data);
    return data;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The request timed out. Check the API and try again.", 408, "REQUEST_TIMEOUT");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function fetchFunds(): Promise<SecFund[]> {
  const payload = await requestJson<{ data_source: "sec_open_data"; funds: SecFund[] }>("/api/funds");
  return payload.funds;
}

export async function fetchDataStatus(): Promise<DataStatus> {
  return requestJson<DataStatus>("/api/data-status");
}

// The longest continuous date range where every given fund has a complete
// NAV observation at the requested frequency -- computed server-side with
// the exact same alignment/completeness rules the optimizer applies, since a
// naive client-side "latest nav_start .. earliest nav_end" intersection can
// still contain a real gap (e.g. the 2024-06 to 2024-11 SEC-wide incident).
export async function fetchTestableRange(
  projIds: string[],
  frequency: DataFrequency = "monthly"
): Promise<{ start: string | null; end: string | null }> {
  if (!projIds.length) return { start: null, end: null };
  const params = new URLSearchParams({ proj_ids: projIds.join(","), frequency });
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

export async function runOptimize(payload: OptimizeRequest): Promise<OptimizeResult> {
  return requestJson<OptimizeResult>(
    "/api/optimize",
    { method: "POST", body: JSON.stringify(payload) },
    OPTIMIZE_REQUEST_TIMEOUT_MS
  );
}

export async function fetchOptimizeByRunId(runId: string): Promise<OptimizeRunResult> {
  return requestJson<OptimizeRunResult>(`/api/optimize/${encodeURIComponent(runId)}`);
}
