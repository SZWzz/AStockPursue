/** API contract types — shared between api.ts and consuming components. */

// --- Upload ---

export interface UploadResult {
  status: string;
  file_path: string;
  filename: string;
}

// --- Swarm types ---

export interface SwarmPreset {
  name: string;
  title: string;
  description: string;
  agent_count: number;
  variables: { name: string; description: string; required: boolean }[];
}

export interface SwarmRunSummary {
  id: string;
  preset_name: string;
  status: string;
  created_at: string;
  task_count: number;
  completed_count: number;
}

// --- LLM / Data Source types ---

export interface LLMProviderOption {
  name: string;
  label: string;
  api_key_env?: string | null;
  base_url_env: string;
  default_model: string;
  default_base_url: string;
  api_key_required: boolean;
  auth_type?: string;
  login_command?: string | null;
}

export interface LLMSettings {
  provider: string;
  model_name: string;
  base_url: string;
  api_key_env?: string | null;
  api_key_configured: boolean;
  api_key_hint?: string | null;
  api_key_required: boolean;
  temperature: number;
  timeout_seconds: number;
  max_retries: number;
  reasoning_effort: string;
  providers: LLMProviderOption[];
}

export interface UpdateLLMSettingsRequest {
  provider: string;
  model_name: string;
  base_url: string;
  api_key?: string;
  clear_api_key?: boolean;
  temperature: number;
  timeout_seconds: number;
  max_retries: number;
  reasoning_effort?: string;
}

export interface DataSourceSettings {
  tushare_token_configured: boolean;
  tushare_token_hint?: string | null;
  okx_api_key_configured: boolean;
  okx_secret_key_configured: boolean;
  okx_passphrase_configured: boolean;
  twelvedata_api_key_configured: boolean;
  finnhub_api_key_configured: boolean;
  tiingo_api_key_configured: boolean;
  akshare_available: boolean;
  akshare_version: string;
  yfinance_available: boolean;
  tencent_available: boolean;
  ccxt_available: boolean;
  coingecko_available: boolean;
  futu_available: boolean;
  global_indices_available: boolean;
  commodities_available: boolean;
}

export interface UpdateDataSourceSettingsRequest {
  tushare_token?: string;
  clear_tushare_token?: boolean;
  futu_host?: string;
  futu_port?: string;
  twelvedata_api_key?: string;
  clear_twelvedata?: boolean;
  finnhub_api_key?: string;
  clear_finnhub?: boolean;
}

export interface DataSourceLoaderStatus {
  name: string;
  display: string;
  markets: string[];
  available: boolean;
  requires_auth: boolean;
  health?: { score?: number; avg_latency_ms?: number; consecutive_failures?: number };
}

// --- Run / chart types ---

export interface RunListItem {
  run_id: string;
  status: string;
  created_at: string;
  prompt?: string;
  total_return?: number;
  sharpe?: number;
  codes?: string[];
  start_date?: string;
  end_date?: string;
}

export interface PriceBar {
  time: string;
  timestamp?: string;
  code?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TradeMarker {
  time: string;
  timestamp?: string;
  code?: string;
  side: "BUY" | "SELL";
  price: number;
  qty?: number;
  reason?: string;
  text?: string;
}

export interface EquityPoint {
  time: string;
  equity: number;
  drawdown: number;
}

export interface ValidationData {
  monte_carlo?: {
    actual_sharpe: number;
    actual_max_dd: number;
    p_value_sharpe: number;
    p_value_max_dd: number;
    simulated_sharpe_mean: number;
    simulated_sharpe_std: number;
    simulated_sharpe_p5: number;
    simulated_sharpe_p95: number;
    n_simulations: number;
    n_trades: number;
    error?: string;
  };
  bootstrap?: {
    observed_sharpe: number;
    ci_lower: number;
    ci_upper: number;
    median_sharpe: number;
    prob_positive: number;
    confidence: number;
    n_bootstrap: number;
    error?: string;
  };
  walk_forward?: {
    n_windows: number;
    windows: Array<{
      window: number;
      start: string;
      end: string;
      return: number;
      sharpe: number;
      max_dd: number;
      trades: number;
      win_rate: number;
    }>;
    profitable_windows: number;
    consistency_rate: number;
    return_mean: number;
    return_std: number;
    sharpe_mean: number;
    sharpe_std: number;
    error?: string;
  };
}

export interface RunData {
  status: string;
  run_id: string;
  prompt?: string;
  elapsed_seconds?: number;
  run_directory?: string;
  run_stage?: string;
  run_context?: Record<string, unknown>;

  metrics?: BacktestMetrics;
  artifacts?: ArtifactInfo[];
  run_card?: RunCard;
  validation?: ValidationData;

  price_series?: Record<string, PriceBar[]>;
  indicator_series?: Record<string, Record<string, IndicatorPoint[]>>;
  trade_markers?: TradeMarker[];
  equity_curve?: EquityPoint[];
  trade_log?: Array<Record<string, string>>;
  run_logs?: Array<{ source?: string; line_number?: number; message?: string }>;
}

export interface RunCard {
  schema_version?: string;
  generated_at?: string;
  run_dir?: string;
  backtest?: Record<string, unknown>;
  reproducibility?: Record<string, unknown>;
  data_sources?: string[];
  metrics?: Record<string, unknown>;
  validation?: unknown;
  warnings?: string[];
  artifacts?: RunCardArtifact[];
  [key: string]: unknown;
}

export interface RunCardArtifact {
  path: string;
  size_bytes: number;
  sha256: string;
}

export interface BacktestMetrics {
  final_value: number;
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  sharpe: number;
  win_rate: number;
  trade_count: number;
  [key: string]: number;
}

export interface IndicatorPoint {
  time: string;
  value: number;
}

export interface ArtifactInfo {
  name: string;
  path: string;
  type: string;
  size: number;
  exists: boolean;
}

export interface PineScriptResult {
  exists: boolean;
  content: string | null;
}

// --- Session types ---

export interface SessionItem {
  session_id: string;
  title?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  last_attempt_id?: string;
}

export interface MessageItem {
  message_id: string;
  session_id: string;
  role: string;
  content: string;
  created_at: string;
  linked_attempt_id?: string;
  metadata?: Record<string, unknown>;
}

// --- Alpha Zoo types ---

export interface AlphaListParams {
  zoo?: string;
  theme?: string;
  universe?: string;
  limit?: number;
}

export interface AlphaSummary {
  id: string;
  zoo: string;
  theme: string[];
  universe: string[];
  nickname?: string;
  decay_horizon?: number | null;
  min_warmup_bars?: number | null;
  requires_sector?: boolean;
}

export interface AlphaListResponse {
  status: string;
  alphas: AlphaSummary[];
  total: number;
  returned: number;
  truncated: boolean;
}

export interface AlphaDetail {
  id: string;
  zoo: string;
  module_path?: string;
  meta: Record<string, unknown>;
}

export interface AlphaDetailResponse {
  status: string;
  alpha: AlphaDetail;
  source_code: string;
}

export interface AlphaBenchRequest {
  zoo: string;
  universe: string;
  period: string;
  top?: number;
}

export interface AlphaBenchTopRow {
  id: string;
  ic_mean: number;
  ir: number;
  theme: string[];
  formula_latex: string;
  category: "alive" | "reversed" | "dead";
}

export interface AlphaBenchResult {
  alive: number;
  reversed: number;
  dead: number;
  skipped?: number;
  n_alphas_tested?: number;
  n_skipped?: number;
  top5_by_ir: AlphaBenchTopRow[];
  dead_examples: AlphaBenchTopRow[];
  by_theme: Record<string, { alive: number; reversed: number; dead: number }>;
  meta?: Record<string, unknown>;
}

export interface BenchHistoryItem {
  run_id: string;
  zoo: string;
  universe: string;
  period: string;
  top: number;
  alive: number;
  reversed: number;
  dead: number;
  n_alphas_tested: number;
  n_skipped: number;
  wall_seconds: number;
  created_at: string;
}

export interface BenchHistoryDetail extends BenchHistoryItem {
  user_id: number;
  by_theme: Record<string, { alive: number; reversed: number; dead: number }>;
  top5_by_ir: AlphaBenchTopRow[];
  dead_examples: AlphaBenchTopRow[];
  meta: Record<string, unknown>;
}

// --- Minute-line (分时图) types ---

export interface MinuteBar {
  time: string;
  price: number;
  volume: number;
  amount: number;
}

export interface MinuteLineData {
  symbol: string;
  date: string;
  adjustedDate?: string | null;
  available: boolean;
  reason?: string;
  preClose?: number;
  minutes: MinuteBar[];
}

// --- Trading Dashboard types ---

export interface TradingOrder {
  id: number;
  user_id: number;
  symbol: string;
  side: "buy" | "sell";
  order_type: "market" | "limit";
  qty: number;
  price: number;
  status: "active" | "filled" | "cancelled";
  created_at: string;
  filled_qty: number;
  avg_price: number;
}

export interface CreateOrderRequest {
  symbol: string;
  side: "buy" | "sell";
  order_type: "market" | "limit";
  qty: number;
  price?: number;
}

export interface BrokerStatus {
  connected: boolean;
  host: string;
  port: number;
  error?: string;
}

export interface BrokerAccount {
  available: boolean;
  account?: Record<string, unknown>;
  error?: string;
}

export interface BrokerPosition {
  code?: string;
  name?: string;
  qty?: number;
  cost_price?: number;
  current_price?: number;
  market_value?: number;
  pnl?: number;
  [key: string]: unknown;
}

export interface NotifyConfig {
  enabled?: boolean;
  channels?: NotifyChannel[];
}

export interface NotifyChannel {
  type: string;
  target: string;
  enabled: boolean;
}

export interface OptimizeRunRequest {
  method: "grid" | "random" | "bayesian";
  params: Record<string, unknown>;
  codes: string[];
  strategy_code?: string;
}

export interface OptimizeProgress {
  job_id: string;
  progress: number;
  status: string;
  error?: string;
}

export interface OptimizeResult {
  job_id: string;
  status: string;
  result?: {
    best_params: Record<string, unknown>;
    best_score: number;
    iterations: number;
    sharpe: number;
    total_return: number;
    max_drawdown: number;
  } | null;
}

export interface IndexItem {
  code: string;
  name: string;
  price: number;
  change_pct: number;
}

export interface NewsItem {
  title: string;
  url: string;
  source: string;
  source_label?: string;       // human-readable Chinese label (e.g. "东财个股")
  summary: string;
  published_at: string;
  sentiment_score?: number;    // 0=negative, 1=positive
  sentiment_label?: string;    // "positive" | "neutral" | "negative"
}

export interface StockSentiment {
  symbol: string;
  sentiment_mean: number;
  sentiment_std: number;
  news_count: number;
  trending_score: number;
  recent_articles?: NewsItem[];
}

export interface TrendingTopic {
  topic: string;
  count: number;
  sentiment_mean: number;
  trending_score: number;
}

export interface MarketSentiment {
  overall_sentiment: number;
  vix: { current: number; level: string; trend: string };
  dxy: { current: number; level: string; trend: string };
  yield_spread: { spread: number; level: string; signal: string };
  fear_greed: { value: number; classification: string };
  news_sentiment_mean: number;
  news_sentiment_count: number;
}

export interface SourceFreshness {
  fresh: boolean | null;
  last_update: string | null;
  count_24h: number;
  label: string;
  category: string;
  ttl_seconds: number;
}

export interface SourceInfo {
  id: string;
  label: string;
  category: string;
}

export interface WSFeedStatus {
  available: boolean;
  error?: string;
}

// --- Factor Mining types ---

export interface GpConfig {
  population_size: number;
  generations: number;
  tournament_size: number;
  crossover_prob: number;
  mutation_prob: number;
  fitness_metric: "ic_mean" | "rank_ic" | "sharpe" | "composite";
  complexity_penalty: "aic" | "bic" | "none";
  use_tiered_operators?: boolean;
  use_hybrid_init?: boolean;
  use_kb?: boolean;
  fdr_alpha?: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  universe: string[];
}

export interface GpProgress {
  job_id?: string;
  progress?: number;
  current_generation?: number;
  total_generations?: number;
  best_ic_so_far?: number;
  status?: string;
  stage?: string;
  message?: string;
}

export interface GpResult {
  job_id: string;
  status: string;
  result?: {
    best_individuals: FactorCandidate[];
    generation_history: GenerationSnapshot[];
    best_test_ic: number;
    runtime_seconds: number;
  };
  candidates?: FactorCandidate[];
  candidates_count?: number;
  config?: Record<string, unknown>;
  error?: string;
  data_source?: string;
  data_source_detail?: string;
}

export interface GenerationSnapshot {
  generation: number;
  best_fitness: number;
  mean_fitness: number;
  std_fitness: number;
  best_ic: number;
  diversity: number;
  best_formula?: string;
  best_expression_json?: Record<string, unknown>;
  best_complexity?: number;
  gen_seconds?: number;
  fitness_distribution?: FitnessDistribution;
  elite_lineage?: EliteEntry[];
  data_source?: string;
}

export interface FitnessDistribution {
  bins: number[];
  counts: number[];
  min: number;
  max: number;
  median: number;
  q25: number;
  q75: number;
}

export interface EliteEntry {
  formula: string;
  expression_json?: Record<string, unknown>;
  first_seen_gen: number;
  last_seen_gen: number;
  survival_gens: number;
  best_fitness: number;
  best_ic: number;
  test_ir: number;
  complexity: number;
  rank: number;
}

export interface FactorCandidate {
  id: string;
  run_id?: string;
  name: string;
  formula: string;
  expression_json?: Record<string, unknown>;
  train_ic: number;
  train_fitness?: number;
  test_ic: number;
  test_ir: number;
  complexity: number;
  is_promoted: boolean;
  promoted_zoo_id?: string;
  created_at?: string;
  source?: string;
  description?: string;
  confidence?: number;
}

export interface ValidationResult {
  syntax_valid: boolean;
  lookahead_clean: boolean;
  coverage: number;
  nan_ratio: number;
  inf_count: number;
  ic_stability: number[];
  max_correlation_with_zoo: number;
  correlation_details?: { factor_id: string; correlation: number }[];
  warnings: string[];
  passed?: boolean;
}

export interface MiningRunSummary {
  id: string;
  type: string;
  status: string;
  config?: Record<string, unknown>;
  candidates_count?: number;
  created_at?: string;
}
