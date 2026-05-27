import { authHeaders, withAuthQuery } from "@/lib/apiAuth";
import type {
  AlphaBenchRequest,
  AlphaBenchResult,
  AlphaBenchTopRow,
  BenchHistoryDetail,
  BenchHistoryItem,
  AlphaDetail,
  AlphaDetailResponse,
  AlphaListParams,
  AlphaListResponse,
  AlphaSummary,
  ArtifactInfo,
  BacktestMetrics,
  DataSourceSettings,
  EquityPoint,
  IndicatorPoint,
  LLMProviderOption,
  LLMSettings,
  MessageItem,
  PineScriptResult,
  PriceBar,
  RunCard,
  RunCardArtifact,
  RunData,
  RunListItem,
  SessionItem,
  SwarmPreset,
  SwarmRunSummary,
  TradeMarker,
  UpdateDataSourceSettingsRequest,
  UpdateLLMSettingsRequest,
  UploadResult,
  ValidationData,
} from "@/types/api";

export type {
  AlphaBenchRequest,
  AlphaBenchResult,
  AlphaBenchTopRow,
  BenchHistoryDetail,
  BenchHistoryItem,
  AlphaDetail,
  AlphaDetailResponse,
  AlphaListParams,
  AlphaListResponse,
  AlphaSummary,
  ArtifactInfo,
  BacktestMetrics,
  DataSourceSettings,
  EquityPoint,
  IndicatorPoint,
  LLMProviderOption,
  LLMSettings,
  MessageItem,
  PineScriptResult,
  PriceBar,
  RunCard,
  RunCardArtifact,
  RunData,
  RunListItem,
  SessionItem,
  SwarmPreset,
  SwarmRunSummary,
  TradeMarker,
  UpdateDataSourceSettingsRequest,
  UpdateLLMSettingsRequest,
  UploadResult,
  ValidationData,
};

const BASE = "/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const AUTH_REQUIRED_MESSAGE =
  "Remote API access requires an API key. Add it in Settings, or run the backend on localhost for local-only use.";

export function isAuthRequiredError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

export async function errorFromResponse(res: Response): Promise<ApiError> {
  let detail = `HTTP ${res.status}`;
  try {
    const body = await res.json();
    detail = body.detail || body.message || detail;
  } catch { /* ignore */ }
  if (res.status === 401 || res.status === 403) {
    detail = AUTH_REQUIRED_MESSAGE;
  }
  return new ApiError(detail, res.status);
}

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const { headers, ...rest } = options ?? {};
  const mergedHeaders: Record<string, string> = { "Content-Type": "application/json", ...authHeaders() };
  if (headers) {
    new Headers(headers).forEach((value, key) => {
      mergedHeaders[key] = value;
    });
  }
  const res = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: mergedHeaders,
  });
  if (!res.ok) {
    throw await errorFromResponse(res);
  }
  const ct = res.headers.get("content-type") || "";
  const text = await res.text();
  if (!text) return {} as T;
  try {
    return JSON.parse(text);
  } catch {
    const preview = text.slice(0, 150).replace(/\s+/g, " ").trim();
    const hint = ct.includes("text/html") ? " (got HTML — check that the API path exists)" : "";
    throw new ApiError(`Unexpected response from ${path}: ${preview || "(empty)"}${hint}`, res.status);
  }
}

async function uploadFile(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", headers: authHeaders(), body: form });
  if (!res.ok) {
    throw await errorFromResponse(res);
  }
  try {
    return await res.json();
  } catch {
    throw new ApiError(`Unexpected response from server (${res.status} ${res.statusText})`, res.status);
  }
}

/** SSE token cache for short-lived EventSource URLs. */
let _sseTokenPromise: Promise<string> | null = null;

/** Get or refresh the short-lived SSE token. */
async function _getSseToken(): Promise<string> {
  if (!_sseTokenPromise) {
    _sseTokenPromise = api.getSseToken().then(r => r.token).finally(() => {
      _sseTokenPromise = null;
    });
  }
  return _sseTokenPromise;
}

/** Build an SSE URL with a short-lived JWT in the query string.
 *
 * Uses a dedicated 5-minute SSE token instead of the long-lived session
 * JWT, so any leakage via server/proxy logs has a limited damage window.
 */
export async function sseUrlWithToken(path: string): Promise<string> {
  const token = await _getSseToken();
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}jwt=${encodeURIComponent(token)}`;
}

export const api = {
  uploadFile,
  listRuns: () => request<RunListItem[]>("/runs"),
  getRun: (id: string) => request<RunData>(`/runs/${id}`),
  getRunCode: (id: string) => request<Record<string, string>>(`/runs/${id}/code`),
  getRunPine: (id: string) => request<PineScriptResult>(`/runs/${id}/pine`),
  listSessions: () => request<SessionItem[]>("/sessions"),
  createSession: (title?: string) => request<SessionItem>("/sessions", { method: "POST", body: JSON.stringify({ title: title || "" }) }),
  deleteSession: (sid: string) => request<{ status: string }>(`/sessions/${sid}`, { method: "DELETE" }),
  renameSession: (sid: string, title: string) => request<{ status: string }>(`/sessions/${sid}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  sendMessage: (sid: string, content: string) => request<{ message_id: string; attempt_id: string }>(`/sessions/${sid}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
  cancelSession: (sid: string) => request<{ status: string }>(`/sessions/${sid}/cancel`, { method: "POST" }),
  getSessionMessages: (sid: string) => request<MessageItem[]>(`/sessions/${sid}/messages`),
  sseUrl: (sid: string) => withAuthQuery(`${BASE}/sessions/${sid}/events`),

  // Swarm API
  listSwarmPresets: () => request<SwarmPreset[]>("/swarm/presets"),
  createSwarmRun: (preset_name: string, user_vars: Record<string, string>) =>
    request<{ id: string; status: string }>("/swarm/runs", {
      method: "POST",
      body: JSON.stringify({ preset_name, user_vars }),
    }),
  listSwarmRuns: () => request<SwarmRunSummary[]>("/swarm/runs"),
  getSwarmRun: (id: string) => request<Record<string, unknown>>(`/swarm/runs/${id}`),
  swarmSseUrl: (id: string) => withAuthQuery(`${BASE}/swarm/runs/${id}/events`),
  cancelSwarmRun: (id: string) =>
    request<{ status: string }>(`/swarm/runs/${id}/cancel`, { method: "POST" }),
  getLLMSettings: () => request<LLMSettings>("/settings/llm"),
  updateLLMSettings: (settings: UpdateLLMSettingsRequest) =>
    request<LLMSettings>("/settings/llm", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  getDataSourceSettings: () => request<DataSourceSettings>("/settings/data-sources"),
  updateDataSourceSettings: (settings: UpdateDataSourceSettingsRequest) =>
    request<DataSourceSettings>("/settings/data-sources", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),

  // Alpha Zoo API
  listAlphas: (params: AlphaListParams = {}) => {
    const q = new URLSearchParams();
    if (params.zoo) q.set("zoo", params.zoo);
    if (params.theme) q.set("theme", params.theme);
    if (params.universe) q.set("universe", params.universe);
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<AlphaListResponse>(`/alpha/list${qs ? `?${qs}` : ""}`);
  },
  getAlpha: (alphaId: string) =>
    request<AlphaDetailResponse>(`/alpha/${encodeURIComponent(alphaId)}`),
  createAlphaBench: (body: AlphaBenchRequest) =>
    request<{ status: string; job_id: string }>("/alpha/bench", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  alphaBenchStreamUrl: (jobId: string) =>
    withAuthQuery(`${BASE}/alpha/bench/${encodeURIComponent(jobId)}/stream`),
  cancelAlphaBench: (jobId: string) =>
    request<{ status: string; job_id: string }>(`/alpha/bench/${encodeURIComponent(jobId)}/cancel`, { method: "POST" }),
  listBenchHistory: (limit = 20, offset = 0) =>
    request<{ status: string; history: BenchHistoryItem[]; total: number }>(`/alpha/bench/history?limit=${limit}&offset=${offset}`),
  getBenchHistoryDetail: (runId: string) =>
    request<{ status: string; run: BenchHistoryDetail }>(`/alpha/bench/history/${encodeURIComponent(runId)}`),
  deleteBenchHistory: (runId: string) =>
    request<{ status: string }>(`/alpha/bench/history/${encodeURIComponent(runId)}`, { method: "DELETE" }),

  // Admin / User management
  listUsers: () => request<{ users: Array<{ id: number; username: string; email: string; role: string; created_at: string; llm_provider: string; llm_model: string; tushare_configured: boolean }> }>("/admin/users"),
  deleteUser: (id: number) => request<{ status: string }>(`/admin/users/${id}`, { method: "DELETE" }),

  // Correlation
  getCorrelation: (params: { codes: string; days: number; method: string }) => {
    const q = `codes=${encodeURIComponent(params.codes)}&days=${params.days}&method=${params.method}`;
    return request<{ labels: string[]; matrix: number[][] }>(`/correlation?${q}`);
  },

  // OHLCV
  getOHLCV: (params: { symbol: string; start_date: string; end_date: string; source: string; interval: string }) => {
    const q = new URLSearchParams(params).toString();
    return request<{ symbol: string; bars: PriceBar[]; source: string }>(`/stock/ohlcv?${q}`);
  },

  // SSE token (short-lived JWT for EventSource query param)
  getSseToken: () => request<{ token: string; expires_in_minutes: number }>("/api/sse-token"),

  // Skill management
  getSkillSettings: () => request<{ skills: Array<{ name: string; description: string; category: string; enabled: boolean; source: "builtin" | "user" }>; total: number; enabled_count: number }>("/settings/skills"),
  updateSkillSettings: (disabled_skills: string[]) => request<{ ok: boolean }>("/settings/skills", { method: "PUT", body: JSON.stringify({ disabled_skills }) }),
  importSkill: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${BASE}/settings/skills/import`, { method: "POST", headers: authHeaders(), body: form }).then(r => r.json()) as Promise<{ ok: boolean; name: string }>;
  },
  deleteSkill: (name: string) => request<{ ok: boolean }>(`/settings/skills/${encodeURIComponent(name)}`, { method: "DELETE" }),
  getMcpSettings: () => request<{ service_name: string; transport: string; sse_port: number; shell_tools_enabled: boolean; config_path: string; install_cmd: string }>("/settings/mcp"),
  updateMcpSettings: (payload: Record<string, unknown>) => request<{ ok: boolean }>("/settings/mcp", { method: "PUT", body: JSON.stringify(payload) }),
};
