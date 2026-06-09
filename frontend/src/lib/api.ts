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
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestMetrics,
  BrokerAccount,
  BrokerCredential,
  BrokerInfo,
  BrokerStatus,
  CreateOrderRequest,
  DataSourceLoaderStatus,
  DataSourceSettings,
  EquityPoint,
  IndexItem,
  IndicatorPoint,
  LLMProviderOption,
  LLMSettings,
  MarketSentiment,
  MessageItem,
  MinuteBar,
  MinuteLineData,
  NewsItem,
  NotifyChannel,
  NotifyConfig,
  OptimizeProgress,
  OptimizeResult,
  OptimizeRunRequest,
  PineScriptResult,
  PriceBar,
  RunCard,
  RunCardArtifact,
  RunData,
  RunListItem,
  SessionItem,
  SourceFreshness,
  StockSentiment,
  SwarmPreset,
  SwarmRunSummary,
  TradeMarker,
  TradingOrder,
  TrendingTopic,
  UpdateDataSourceSettingsRequest,
  UpdateLLMSettingsRequest,
  UploadResult,
  ValidationData,
  WSFeedStatus,
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
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestMetrics,
  BrokerAccount,
  BrokerCredential,
  BrokerInfo,
  BrokerStatus,
  CreateOrderRequest,
  DataSourceSettings,
  EquityPoint,
  IndexItem,
  IndicatorPoint,
  LLMProviderOption,
  LLMSettings,
  MarketSentiment,
  MessageItem,
  MinuteBar,
  MinuteLineData,
  NewsItem,
  NotifyChannel,
  NotifyConfig,
  OptimizeProgress,
  OptimizeResult,
  OptimizeRunRequest,
  PineScriptResult,
  PriceBar,
  RunCard,
  RunCardArtifact,
  RunData,
  RunListItem,
  SessionItem,
  SourceFreshness,
  StockSentiment,
  SwarmPreset,
  SwarmRunSummary,
  TradeMarker,
  TradingOrder,
  TrendingTopic,
  UpdateDataSourceSettingsRequest,
  UpdateLLMSettingsRequest,
  UploadResult,
  ValidationData,
  WSFeedStatus,
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
  const { headers, body, ...rest } = options ?? {};
  // Detect FormData — browser sets correct Content-Type with boundary automatically
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  const mergedHeaders: Record<string, string> = isFormData
    ? { ...authHeaders() }
    : { "Content-Type": "application/json", ...authHeaders() };
  if (headers) {
    new Headers(headers).forEach((value, key) => {
      mergedHeaders[key] = value;
    });
  }
  const res = await fetch(`${BASE}${path}`, {
    body,
    ...rest,
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

  // ── Backtest History (PG-backed) ──────────────────────────────
  listBacktestHistory: (limit = 50, offset = 0) =>
    request<{ runs: BacktestRunSummary[]; total: number }>(
      `/api/backtest-history?limit=${limit}&offset=${offset}`
    ),
  getBacktestHistory: (id: string) =>
    request<BacktestRunDetail>(`/api/backtest-history/${id}`),
  deleteBacktestHistory: (id: string) =>
    request<{ ok: boolean }>(`/api/backtest-history/${id}`, { method: "DELETE" }),

  // ── Page → Workflow bridge ────────────────────────────────────
  createWorkflowFromPage: (body: { source_page: string; config: Record<string, unknown>; project_id?: string }) =>
    request<{ workflow_id: string; project_id: string; redirect: string }>(
      "/workflows/from-page",
      { method: "POST", body: JSON.stringify(body) },
    ),

  getLLMSettings: () => request<LLMSettings>("/settings/llm"),
  updateLLMSettings: (settings: UpdateLLMSettingsRequest) =>
    request<LLMSettings>("/settings/llm", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  getDataSourceSettings: () => request<DataSourceSettings>("/settings/data-sources"),
  getDataSourceStatus: () => request<{loaders: DataSourceLoaderStatus[]}>("/settings/data-source-status"),
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

  // -- Fundamental data --------------------------------------------------
  getStockFinance: (code: string) =>
    request<{ symbol: string; available: boolean; fields: Record<string, number | string>; field_count: number }>(`/stock/finance/${encodeURIComponent(code)}`),
  getStockF10: (code: string, name = "最新提示") =>
    request<{ symbol: string; name: string; available: boolean; text: string | null }>(`/stock/f10/${encodeURIComponent(code)}?name=${encodeURIComponent(name)}`),
  getStockF10All: (code: string) =>
    request<{ symbol: string; categories: Record<string, string | null>; available_count: number }>(`/stock/f10/${encodeURIComponent(code)}/all`),
  getStockFinancials: (code: string) =>
    request<{ symbol: string; income_statement: any[]; balance_sheet: any[]; cash_flow: any[]; income_count: number; balance_count: number; cashflow_count: number }>(`/stock/financials/${encodeURIComponent(code)}`),
  getStockValuation: (code: string, params: { price: number; eps_current: number; eps_forecast: number; target_pe?: number }) => {
    const q = new URLSearchParams({ price: String(params.price), eps_current: String(params.eps_current), eps_forecast: String(params.eps_forecast) });
    if (params.target_pe) q.set("target_pe", String(params.target_pe));
    return request<Record<string, unknown>>(`/stock/valuation/${encodeURIComponent(code)}?${q}`);
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

  // Stock minuteline (分时图)
  getMinuteLine: (symbol: string, date?: string) => {
    const params = new URLSearchParams({ symbol });
    if (date) params.set("date", date);
    return request<MinuteLineData>(`/stock/minute-line?${params}`);
  },

  // --- Trading Dashboard ---

  // Orders
  listOrders: (status = "") => request<{ orders: TradingOrder[] }>(`/trading/orders${status ? `?status=${status}` : ""}`),
  createOrder: (body: CreateOrderRequest) => request<{ ok: boolean; order: TradingOrder }>("/trading/orders", { method: "POST", body: JSON.stringify(body) }),
  cancelOrder: (orderId: number) => request<{ ok: boolean; order: TradingOrder }>(`/trading/orders/${orderId}/cancel`, { method: "POST" }),

  // Broker
  getBrokerStatus: () => request<BrokerStatus>("/trading/broker/status"),
  getBrokerAccount: () => request<BrokerAccount>("/trading/broker/account"),
  getBrokerPositions: () => request<{ positions: Record<string, unknown>[]; error?: string }>("/trading/broker/positions"),
  // Multi-Broker
  getBrokerList: () => request<{ brokers: BrokerInfo[] }>("/trading/broker/list"),
  getBrokerCredentials: () => request<{ credentials: BrokerCredential[]; error?: string }>("/trading/broker/credentials"),
  saveBrokerCredential: (body: { exchange_id: string; label?: string; api_key?: string; secret_key?: string; passphrase?: string; testnet?: boolean }) =>
    request<{ status: string; exchange_id: string }>("/trading/broker/credentials", { method: "POST", body: JSON.stringify(body) }),
  deleteBrokerCredential: (id: number) => request<{ status: string }>(`/trading/broker/credentials/${id}`, { method: "DELETE" }),
  testBrokerConnection: (body: { exchange_id: string; testnet?: boolean }) =>
    request<BrokerStatus>("/trading/broker/test", { method: "POST", body: JSON.stringify(body) }),
  getBrokerPositionsMulti: (exchangeId: string, testnet?: boolean) =>
    request<{ positions: Record<string, unknown>[]; error?: string }>(`/trading/broker/${exchangeId}/positions${testnet !== undefined ? `?testnet=${testnet}` : ""}`),
  getBrokerBalanceMulti: (exchangeId: string, testnet?: boolean) =>
    request<{ balance: Record<string, unknown>; error?: string }>(`/trading/broker/${exchangeId}/balance${testnet !== undefined ? `?testnet=${testnet}` : ""}`),

  // Notify
  getNotifyConfig: () => request<NotifyConfig>("/trading/notify/config"),
  updateNotifyConfig: (config: NotifyConfig) => request<{ ok: boolean; config: NotifyConfig }>("/trading/notify/config", { method: "PUT", body: JSON.stringify(config) }),
  testNotify: (channel: string, target: string) => request<{ ok: boolean; message?: string; error?: string }>("/trading/notify/test", { method: "POST", body: JSON.stringify({ channel, target }) }),

  // Optimize
  startOptimize: (body: OptimizeRunRequest) => request<{ ok: boolean; job_id: string }>("/trading/optimize/run", { method: "POST", body: JSON.stringify(body) }),
  optimizeStreamUrl: (jobId: string) => withAuthQuery(`${BASE}/trading/optimize/${encodeURIComponent(jobId)}/stream`),
  getOptimizeResult: (jobId: string) => request<OptimizeResult>(`/trading/optimize/${encodeURIComponent(jobId)}/result`),

  // WS Feed
  getWSFeedStatus: () => request<WSFeedStatus>("/trading/ws-feed/status"),
  subscribeWSFeed: (symbols: string[]) => request<{ ok: boolean; symbols: string[] }>("/trading/ws-feed/subscribe", { method: "POST", body: JSON.stringify({ symbols }) }),

  // Indices
  getIndices: () => request<{ indices: IndexItem[] }>("/trading/indices"),
  saveIndicesConfig: (indices: IndexItem[]) => request<{ ok: boolean }>("/trading/indices/config", { method: "POST", body: JSON.stringify({ indices }) }),

  // News
  getNews: (symbol: string, limit = 20) => request<{ symbol: string; articles: NewsItem[]; source: string; stock_sentiment?: StockSentiment }>(`/trading/news/${encodeURIComponent(symbol)}?limit=${limit}`),

  // News Sentiment
  getNewsFeed: (symbol?: string, limit = 20, source?: string) => {
    const params = new URLSearchParams();
    if (symbol) params.set("symbol", symbol);
    if (source) params.set("source", source);
    params.set("limit", String(limit));
    return request<{ articles: NewsItem[]; total: number; symbol: string }>(`/news/feed?${params}`);
  },
  getStockSentiment: (symbol: string) => request<StockSentiment>(`/news/sentiment/${encodeURIComponent(symbol)}`),
  getTrendingTopics: (limit = 10) => request<{ topics: TrendingTopic[] }>(`/news/trending?limit=${limit}`),
  getMarketSentiment: () => request<MarketSentiment>("/news/market-sentiment"),
  getSourceFreshness: () => request<{ sources: Record<string, SourceFreshness> }>("/news/source-freshness"),
  newsStreamUrl: async (symbol?: string) => {
    const path = symbol
      ? `/news/stream?symbol=${encodeURIComponent(symbol)}`
      : "/news/stream";
    return sseUrlWithToken(path);
  },

  // --- Screener ---
  listScreenerPresets: () => request<any[]>("/screener/presets"),
  saveScreenerPreset: (body: any) => request("/screener/presets", { method: "POST", body: JSON.stringify(body) }),
  deleteScreenerPreset: (id: number) => request(`/screener/presets/${id}`, { method: "DELETE" }),
  runScreener: (body: any) => request("/screener/run", { method: "POST", body: JSON.stringify(body) }),
  aiRecommendScreener: () => request<any>("/screener/ai-recommend", { method: "POST" }),
  screenerBatch: (body: any) => request("/screener/batch", { method: "POST", body: JSON.stringify(body) }),
  getScreenerFields: () => request<any[]>("/screener/fields"),

  // --- Attribution ---
  attributionBrinson: (body: any) => request("/attribution/brinson", { method: "POST", body: JSON.stringify(body) }),
  attributionFactor: (body: any) => request("/attribution/factor", { method: "POST", body: JSON.stringify(body) }),
  attributionSector: (body: any) => request("/attribution/sector", { method: "POST", body: JSON.stringify(body) }),
  attributionDecomp: (body: any) => request("/attribution/time-series-decomposition", { method: "POST", body: JSON.stringify(body) }),
  attributionFull: (body: any) => request("/attribution/full", { method: "POST", body: JSON.stringify(body) }),

  // --- Scheduler ---
  listSchedulerTasks: () => request("/scheduler/tasks"),
  createSchedulerTask: (body: any) => request("/scheduler/tasks", { method: "POST", body: JSON.stringify(body) }),
  updateSchedulerTask: (id: string, body: any) => request(`/scheduler/tasks/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteSchedulerTask: (id: string) => request(`/scheduler/tasks/${id}`, { method: "DELETE" }),
  pauseSchedulerTask: (id: string) => request(`/scheduler/tasks/${id}/pause`, { method: "POST" }),
  resumeSchedulerTask: (id: string) => request(`/scheduler/tasks/${id}/resume`, { method: "POST" }),
  runSchedulerTaskNow: (id: string) => request(`/scheduler/tasks/${id}/run-now`, { method: "POST" }),
  getSchedulerTaskHistory: (id: string) => request(`/scheduler/tasks/${id}/history`),

  // --- Marketplace ---
  browseMarketplace: (params: any) => {
    const q = new URLSearchParams();
    if (params.market) q.set("market", params.market);
    if (params.category) q.set("category", params.category);
    if (params.sort) q.set("sort", params.sort);
    if (params.limit) q.set("limit", String(params.limit));
    return request(`/marketplace/strategies?${q.toString()}`);
  },
  publishMarketplaceStrategy: (body: any) => request("/marketplace/publish", { method: "POST", body: JSON.stringify(body) }),
  getMarketplaceStrategy: (id: string) => request(`/marketplace/strategy/${id}`),
  rateMarketplaceStrategy: (id: string, body: any) => request(`/marketplace/strategy/${id}/rate`, { method: "POST", body: JSON.stringify(body) }),
  installMarketplaceStrategy: (id: string) => request(`/marketplace/strategy/${id}/install`, { method: "POST" }),
  unpublishMarketplaceStrategy: (id: string) => request(`/marketplace/strategy/${id}`, { method: "DELETE" }),

  // --- Options ---
  optionsBlackScholes: (body: any) => request("/options/black-scholes", { method: "POST", body: JSON.stringify(body) }),
  optionsBinomial: (body: any) => request("/options/binomial", { method: "POST", body: JSON.stringify(body) }),
  optionsImpliedVol: (body: any) => request("/options/implied-volatility", { method: "POST", body: JSON.stringify(body) }),
  optionsVolSurface: (body: any) => request("/options/vol-surface", { method: "POST", body: JSON.stringify(body) }),
  optionsGreeks: (body: any) => request("/options/greeks", { method: "POST", body: JSON.stringify(body) }),

  // --- Strategy Versions ---
  listStrategyVersions: (strategyId: number) => request(`/strategy-versions/${strategyId}`),
  saveStrategyVersion: (strategyId: number, body: any) => request(`/strategy-versions/${strategyId}`, { method: "POST", body: JSON.stringify(body) }),
  getStrategyVersion: (strategyId: number, versionNum: number) => request(`/strategy-versions/${strategyId}/${versionNum}`),
  getStrategyVersionDiff: (strategyId: number, fromV: number, toV: number) => request(`/strategy-versions/${strategyId}/diff/${fromV}/${toV}`),
  revertStrategyVersion: (strategyId: number, versionNum: number) => request(`/strategy-versions/${strategyId}/revert/${versionNum}`, { method: "POST" }),

  // --- Live Bridge ---
  liveBridgePreflight: (runId: string) => request(`/live-bridge/preflight/${runId}`, { method: "POST" }),
  liveBridgePromote: (body: any) => request("/live-bridge/promote", { method: "POST", body: JSON.stringify(body) }),

  // --- Factor Mining ---
  startGpRun: (config: import("@/types/api").GpConfig) => request<{ job_id: string; status: string }>("/factor-mining/gp/start", { method: "POST", body: JSON.stringify(config) }),
  getGpResult: (jobId: string) => request<import("@/types/api").GpResult>(`/factor-mining/gp/${jobId}/result`),
  getGenerationHistory: (jobId: string) => request<import("@/types/api").GenerationSnapshot[]>(`/factor-mining/gp/${jobId}/generations`),
  cancelGpRun: (jobId: string) => request<{ status: string }>(`/factor-mining/gp/${jobId}/cancel`, { method: "POST" }),
  llmExtractText: (text: string) => request<{ candidates: import("@/types/api").FactorCandidate[]; count: number }>("/factor-mining/llm/extract", { method: "POST", body: JSON.stringify({ text }) }),
  llmExtractPdf: (formData: FormData) => request<{ candidates: import("@/types/api").FactorCandidate[]; count: number }>("/factor-mining/llm/extract-pdf", { method: "POST", body: formData }),
  llmDebate: (candidateIds: string[]) => request<{ filtered: import("@/types/api").FactorCandidate[]; original_count: number; filtered_count: number }>("/factor-mining/llm/debate", { method: "POST", body: JSON.stringify({ candidate_ids: candidateIds }) }),
  hybridStart: (config: Record<string, unknown>) => request<{ job_id: string; status: string }>("/factor-mining/hybrid/start", { method: "POST", body: JSON.stringify(config) }),
  fetchCandidates: () => request<{ candidates: import("@/types/api").FactorCandidate[]; total: number }>("/factor-mining/candidates"),
  validateCandidate: (id: string) => request<import("@/types/api").ValidationResult>(`/factor-mining/candidates/${id}/validate`, { method: "POST" }),
  promoteCandidate: (id: string, data: { zoo: string; theme: string; name: string; description: string }) => request<{ ok: boolean; alpha_id: string; message: string }>(`/factor-mining/candidates/${id}/promote`, { method: "POST", body: JSON.stringify(data) }),
  deleteCandidate: (id: string) => request<{ ok: boolean }>(`/factor-mining/candidates/${id}`, { method: "DELETE" }),
  fetchMiningHistory: () => request<{ runs: import("@/types/api").MiningRunSummary[]; total: number }>("/factor-mining/history"),

  // --- Workflow ---
  // Strategy options for workflow node
  listStrategyOptions: () => request<{ strategies: { id: string; name: string; code: string }[] }>("/strategy-lab/options"),
  // Projects
  listProjects: () => request<any[]>("/workflow/projects"),
  createProject: (body: { name: string; description?: string }) => request<any>("/workflow/projects", { method: "POST", body: JSON.stringify(body) }),
  updateProject: (id: string, body: { name?: string; description?: string }) => request<any>(`/workflow/projects/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteProject: (id: string) => request<any>(`/workflow/projects/${id}`, { method: "DELETE" }),
  // Workflows
  listWorkflows: (projectId: string) => request<any[]>(`/workflow/projects/${projectId}/workflows`),
  createWorkflow: (projectId: string, body: { name: string; description?: string }) => request<any>(`/workflow/projects/${projectId}/workflows`, { method: "POST", body: JSON.stringify(body) }),
  getWorkflow: (id: string) => request<any>(`/workflow/workflows/${id}`),
  saveWorkflow: (id: string, body: any) => request<any>(`/workflow/workflows/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteWorkflow: (id: string) => request<any>(`/workflow/workflows/${id}`, { method: "DELETE" }),
  duplicateWorkflow: (id: string, body: { name: string }) => request<any>(`/workflow/workflows/${id}/duplicate`, { method: "POST", body: JSON.stringify(body) }),
  // Execution
  runWorkflow: (id: string, body?: { target_node_id?: string }) => request<any>(`/workflow/workflows/${id}/run`, { method: "POST", body: JSON.stringify(body || {}) }),
  runSingleNode: (wfId: string, nodeId: string, body?: { inputs?: any }) => request<any>(`/workflow/workflows/${wfId}/run/${nodeId}`, { method: "POST", body: JSON.stringify(body || {}) }),
  stopWorkflow: (id: string) => request<any>(`/workflow/workflows/${id}/stop`, { method: "POST" }),
  getWorkflowRun: (runId: string) => request<any>(`/workflow/runs/${runId}`),
  getNodeResult: (runId: string, nodeId: string) => request<any>(`/workflow/runs/${runId}/node/${nodeId}`),
  // Registry
  listNodeTypes: () => request<any[]>("/workflow/node-types"),
  getNodeType: (type: string) => request<any>(`/workflow/node-types/${type}`),
  // Validation
  validateWorkflow: (id: string) => request<any>(`/workflow/workflows/${id}/validate`, { method: "POST" }),
  validateConnection: (body: { source_type: string; target_type: string }) => request<any>("/workflow/validate-connection", { method: "POST", body: JSON.stringify(body) }),
  suggestNext: (body: { source_type: string }) => request<any>("/workflow/suggest-next", { method: "POST", body: JSON.stringify(body) }),
  // Templates
  listTemplates: (category?: string) => request<any[]>(`/workflow/templates${category ? `?category=${category}` : ""}`),
  getTemplate: (id: string) => request<any>(`/workflow/templates/${id}`),
  instantiateTemplate: (id: string, body: { project_id: string; name?: string }) => request<any>(`/workflow/templates/${id}/instantiate`, { method: "POST", body: JSON.stringify(body) }),
  // Version History
  listWorkflowVersions: (id: string) => request<any>(`/workflow/workflows/${id}/versions`),
  restoreWorkflowVersion: (wfId: string, runId: string) => request<any>(`/workflow/workflows/${wfId}/versions/${runId}/restore`, { method: "POST" }),
  // Schedule
  scheduleWorkflow: (id: string, body: { cron_expression: string; name?: string }) => request<any>(`/workflow/workflows/${id}/schedule`, { method: "POST", body: JSON.stringify(body) }),
  // Cleanup
  cleanupWorkflowData: () => request<any>("/workflow/cleanup", { method: "POST" }),

  // Export / Import
  exportWorkflow: (id: string) => request<any>(`/workflow/workflows/${id}/export`),
  importWorkflow: (projectId: string, body: { name: string; nodes: any[]; edges: any[] }) =>
    request<any>("/workflow/import", { method: "POST", body: JSON.stringify({ project_id: projectId, ...body }) }),

  // Batch run
  batchRunWorkflow: (id: string, body: { param_grid: Record<string, any[]> }) =>
    request<any>(`/workflow/workflows/${id}/batch`, { method: "POST", body: JSON.stringify(body) }),

  // Replay
  replayRun: (runId: string) => request<any>(`/workflow/runs/${runId}/replay`, { method: "POST" }),

  // Node I/O preview
  previewNodeRun: (runId: string, nodeId: string) =>
    request<any>(`/workflow/runs/${runId}/node/${nodeId}/preview`),

  // Presets
  listPresets: () => request<any[]>("/workflow/presets"),
};
