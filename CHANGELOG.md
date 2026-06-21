# 更新日志

## [2026.6.21] - 2026-06-21

### Added
- [Agent] Create `AgentLoop` in `services/go/internal/agent/loop.go` -- capability-first execution loop with `MatchThreshold = 0.3`, LLM fallback, and `AgentResult` struct
- [Market] Create `Adapter` interface in `services/go/internal/market/adapter.go` -- unified 5-method interface with context support, `FetchRequest` struct, and `Markets()`/`RequiresAuth()` methods
- [Research] Create `GeopoliticsService` in `services/go/internal/research/geopolitics.go` -- 10 pre-configured GDELT topics (US-China Trade, Taiwan Strait, South China Sea, Russia-Ukraine, Middle East, Energy Security, Semiconductor Supply Chain, Rare Earth, Global Inflation, Emerging Market Debt) with cache-first mock risk assessment, per-topic risk_level/tone/tone_change/vol_change, and `IsAvailable()` always true (P4.4)
- [Research] Create `NorthboundService` in `services/go/internal/research/northbound.go` -- A-share northbound capital flow monitoring with net_inflow_daily/weekly/monthly, cumulative_net_buy, top10_active_stocks, and sector_distribution; cache-first with deterministic mock fallback via hashFloat() (P4.5)
- [Research] Create `NewsService` in `services/go/internal/research/news.go` -- multi-source news aggregation with overall_sentiment, sentiment_change, key_topics, source_count, and 7 deterministic mock articles per symbol; cache-first with mock fallback (P4.6)
- [ML] Create `ModelRegistry` + `Evaluator` in `services/go/internal/ml/` -- SQLite-backed model persistence with CRUD operations, category/status filtering, and deterministic mock evaluation returning Sharpe/MaxDrawdown/WinRate/TotalReturn/IC/IR metrics (P5.1)

### Changed
- [Python] Migrate 22 TODO(P6) markers to Go REST API — workflow nodes (trading, thin, strategy), live_bridge, gp_engine now call Go HTTP endpoints instead of deleted Python modules
- [Python] Add `src/go_http.py` — lightweight HTTP client for Go REST API with X-API-Key auth

### Fixed
- [Python] Fix strategy_nodes Go API field mapping — use "ids" key for list, unwrap {id, result} envelope for backtest results
- [Python] Fix gp_engine fallback data fetching — full universe data now loaded when fallback source is found
- [Python] Fix thin_nodes unused `duration` variable — now passes configured value to Timedelta

### Removed
- [Python] Delete `src/trading/` stub package — all 22 consumers migrated to Go HTTP

## [2026.6.20] - 2026-06-20

### Removed
- [Python] Remove 28 API route files under `src/api/` — replaced by Go HTTP handlers (`services/go/internal/api/handler/`)
- [Python] Remove `api_server.py` FastAPI entry point — replaced by Go HTTP server (port 8899)
- [Python] Remove `papertrade/` package (6 files) — migrated to Go `papertrade.Engine` (state machine + repository + CRUD)
- [Python] Remove 4 test files for deleted API routes (`test_security_auth_api`, `test_settings_api`, `test_upload_api`, `test_upload_security`)
- [Python] Remove `src/trading/brokers/` (5 files) — Binance/OKX/Futu brokers migrated to Go `internal/broker/`
- [Python] Remove `src/trading/engine.py` + `risk_pipeline.py` — migrated to Go `internal/engine/pipeline.go` + `risk.go`
- [Python] Remove 4 test files for deleted trading modules (`test_backtest_integration`, `test_engine_robustness`, `test_risk_pipeline`, `test_trading_engine`)
- [Python] Add TODO(P6) markers in consumer files (live_bridge, trading_nodes, thin_nodes, backtest_driver, strategy_nodes, backtest/engines/__init__) to track remaining Go migration work
- [Python] Remove `src/optimize/` (6 files) — migrated to Go engines; all optimizers (bayesian, grid_search, walk_forward, evolution, random_search) replaced by Go implementations
- [Python] Remove 11 test files for migrated engine/signal/live/runner modules — Go has equivalent test coverage (245 tests)
- [Python] Remove `backtest/engines/` (12 files) — all 8 engine types migrated to Go `internal/engine/`
- [Python] Remove `backtest/runner.py` (46KB) + 10 backtest utility files — backtest orchestration migrated to Go
- [Python] Remove `src/trading/` modules (8 files) — backtest_driver, live_driver, oms, signal_adapter, ws_feed, etc. migrated to Go
- [Python] Remove `src/lab/backtest_bridge.py` + `strategy_backtest_bridge.py` — lab bridges migrated to Go
- [Python] Remove 6 test files for deleted backtest modules
- [Python] Add try/except ImportError guard in gp_engine.py for deleted backtest.runner imports
- [Python] Rewrite `src/trading/__init__.py` as stub with TODO(P6) migration note
- [Go] Remove dead port 8901 from Dockerfile and docker-compose.yml — Go only serves HTTP (8899), gRPC is Python (8902)
- [Go] Remove empty `internal/grpc/` directory — Go is gRPC client only, server is Python

### Added
- [Frontend] Add visual Workflow canvas editor — @xyflow/react DAG with NodePalette, WorkflowCanvas, BaseNode, NodePanel + Zustand workflowStore
- [Frontend] Add Strategy Lab IDE — Monaco code editor, Recharts ChartPanel, BacktestPanel (symbol/date config + run button + metrics display)
- [Frontend] Add IndexTickerBar to Dashboard — real-time WebSocket ticker for A-share indices
- [Frontend] Add multi-mode Screener — Filter/Rank/Score tabs, condition builder (field/operator/value), preset save/load
- [Frontend] Add CodeEditor (Monaco wrapper) and ChartPanel (Recharts equity chart) components for Strategy Lab
- [Frontend] Add i18n keys for Strategy Lab, Screener modes, and workflow labels (en + zh)
- [Frontend] Add @xyflow/react and @monaco-editor/react dependencies
- [Go] Add 503 graceful degradation for factor/workflow/signal handlers when Python gRPC is down — routes always registered
- [Go] Add Workflow list (GET) and save (POST) endpoints with in-memory store
- [Go] Increase seed data preload from 5 to 12 A-share symbols

### Changed
- [Go] Always register factor/workflow/signal API routes regardless of gRPC connection status
- [Frontend] Dashboard KPIs wired to real portfolio API data (was hardcoded)
- [Frontend] Trading PriceTicker wired to market API data (was hardcoded $12.50)
- [Frontend] Strategy Lab backtest POST now includes user's code in request body

### Changed
- [Frontend] Replace workflow detail page with visual DAG canvas editor (3-column: palette + canvas + panel)
- [Frontend] Enhance screenerStore with ScreenMode, conditions array, and presets management

### Fixed
- [Go] Fix nil pointer panic in `NewPostgresBacktestStore` — add nil guard for timescale parameter
- [Go] Fix nil context panic in `NewTimescaleDB` — add nil/empty guards before pgxpool.New

### Added
- [Frontend] Add 5 new financial components: StatCallout (hero numbers), StatusBadge (8 variants), PriceTicker (real-time bar), MarketRow (dense list), DividerSection (section header)
- [Frontend] Add i18n keys for market, screener, and status labels (en + zh)
- [Frontend] Add StatCallout component — large hero number (52px lg / 44px md), 300w/400w mono, transparent bg, arrow trend indicator

### Changed
- [Frontend] Redesign entire frontend from OLED dark/orange theme to Coinbase institutional light theme — white canvas, blue (#0052FF) primary, Inter + JetBrains Mono fonts, hairline-border elevation system, 6px radius, 16px body
- [Frontend] Restyle 19 shadcn/ui Base components for Coinbase light theme — Button h-10/16px, Card border/hairline, Input h-10, Badge semitransparent, Table 40px rows, Tabs underline
- [Frontend] Redesign 12 financial components — KpiCard 44px mono, PositionTable arrows, OrderBook depth bars, chart Coinbase colors
- [Frontend] Adapt 27 pages for light theme — white border cards, StatCallout KPIs, StatusBadge, PriceTicker, DividerSection
- [Frontend] Redesign KpiCard — Coinbase style gray bg (#F7F7F7), 44px 400w mono number, arrow trend indicator; props migrated from sub/trend to change/direction

### Added
- [gRPC] Add shared DataService gRPC client (`src/grpc/data_client.py`) with `get_data_client()` singleton and `fetch_bars()` helper — unified data path for Python callers
- [Portfolio] Add Sizer interface with EqualWeight, Kelly, and RiskParity implementations in Go portfolio sizing package
- [API] Add factor.go, workflow.go, signal.go handlers proxying HTTP to Python gRPC (FactorService, WorkflowService, SignalService); register /api/v1/factor, /api/v1/workflow, /api/v1/signal routes in router.go; wire gRPC connection in main.go
- [gRPC] Add WorkflowService servicer with ExecuteWorkflow and GetNodeResult RPCs
- [gRPC] Add AnalysisService servicer with CalcAttribution, CalcCorrelation, StressTest RPCs
- [Frontend] Add PositionTable component — renders positions via usePositions() SWR hook with shadcn Table (loading/error/empty states, up/down color coding)
- [Frontend] Add OrderForm component — order submission form using useOrderFormStore() Zustand store, POST to /api/trading/orders with toast feedback
- [Frontend] Add paper trading list page (app/paper-trading/page.tsx) — table with Name, Strategy, Status badge, PnL (color-coded), Created date; "New" button creates account via POST /api/papertrading; each row navigates to /paper-trading/[id]
- [Frontend] Add paper trading detail page (app/paper-trading/[id]/page.tsx) — KPI cards (Equity, Return, Drawdown, Trades), EquityChart (8 cols) + TradeTimeline (4 cols), Start/Stop buttons; uses useSWR to fetch /api/papertrading/:id
- [Frontend] Add backtest list page (app/backtest/page.tsx) — table with Name, Strategy, Start/End dates, Return (color-coded), Sharpe, Max Drawdown, Win Rate; "New Backtest" button links to /backtest/new; each row navigates to /backtest/[id]
- [Frontend] Add backtest create form (app/backtest/new/page.tsx) — form with strategy name, symbol, date range, frequency select (daily/hourly), initial capital; POST to /api/backtest; redirects to new backtest on success
- [Frontend] Add backtest detail page (app/backtest/[id]/page.tsx) — 5 KPI cards (Total Return, Sharpe, Max Drawdown, Win Rate, Total Trades), EquityChart + DrawdownChart stacked, TradeTimeline for trade log
- [Frontend] Update useWebSocket hook with matchRoute() for dynamic paper-trading/[id] routes, add /paper-trading channel subscriptions (positions + orders)
- [Frontend] Add BFF API proxy routes for all 12 Go endpoints (trading, backtest, market, broker, portfolio, papertrading, settings, system, analysis, scheduler, screener, factors) — each route forwards JWT-authenticated requests from `/api/<resource>` to `/api/v1/<resource>` on the Go backend
- [Frontend] Add 5 Zustand stores: uiStore (sidebar collapse, persisted), themeStore (layout preset + fontSize, persisted), orderFormStore (order form draft state), screenerStore (conditions + sort), wsStore (WebSocket connection state + subscriptions Map)
- [Frontend] Add OLED theme CSS variables (globals.css) with surface layers, borders, brand, semantic, text, layout, radius, and font tokens; scrollbar styling; zh locale red-up/green-down swap
- [Frontend] Add frontend/lib/constants.ts with OLED color constants, API_BASE and WS_URL environment variables
- [Frontend] Add frontend/lib/utils.ts with cn() class merger, format helpers (price, percent, volume, PnL, datetime), and colorForChange utility
- [Frontend] Add frontend/lib/api-client.ts with apiFetch() wrapper and setApiToken() for JWT-authenticated HTTP calls to the Go backend
- [Frontend] Add frontend/lib/navigation.ts with NavGroup/NavItem interfaces and sidebar navigation config (dashboard, trade, research, market, system sections)
- [Frontend] Add frontend/lib/auth-client.ts with signOut() placeholder stub
- [Frontend] Add Sidebar component (220px fixed sidebar with nav links, active state highlighting, logo, user footer)
- [Frontend] Add Header component (48px fixed header with breadcrumb, notifications bell, user dropdown with logout)
- [Frontend] Add SidebarLayout component (wraps Sidebar + Header + main content area)
- [Frontend] Add root layout with SessionProvider (next-auth), NextIntlClientProvider (i18n), ThemeProvider (OLED dark mode), Toaster (sonner), and Fira fonts from Google Fonts
- [Frontend] Add Fira Sans and Fira Code font loading via Google Fonts preconnect + stylesheet links in root layout
- [Frontend] Add OrderBook component — bid/ask depth visualization with proportional bar fills
- [Frontend] Add TradeTimeline component — chronological trade list with side/price/PnL columns
- [Frontend] Add CorrelationMatrix component — D3 heatmap with diverging color scale
- [Frontend] Add ScreenerGrid component — sortable table for screened stock results
- [Frontend] Add LogViewer component — scrollable log display with monospace formatting
- [Frontend] Add trading panel page (app/trading/page.tsx) — real-time trading with SymbolSearch, OrderForm (3 cols), CandlestickChart (6 cols), OrderBook (3 cols), and PositionTable below
- [Frontend] Add orders list page (app/trading/orders/page.tsx) — orders table with columns for order ID, symbol, side (color-coded), price, quantity, filled qty, status badge
- [Frontend] Add positions page (app/trading/positions/page.tsx) — dedicated positions view wrapping PositionTable with live P&L via WebSocket

### Changed
- [Swarm] Migrate `swarm/grounding.py` `fetch_grounding_data()` from direct `loaders.registry.resolve_loader` to shared gRPC `fetch_bars()` — swarm grounding now uses the same DataService path as the Go core
- [Python] Add TODO(P5-task8) annotations to 7 data-loader call sites not yet migrated to gRPC (stock_routes, ui_services, system_routes, dashboard_routes, gp_engine, backtest_tool, trading_routes)
- [Frontend] Update next.config.ts with createNextIntlPlugin to enable next-intl server-side locale and message resolution
- [Frontend] Update all doc paths from `services/frontend/` to `frontend/` (CLAUDE.md, README.md, README_zh.md)
- [Frontend] Update docker-compose.yml frontend service: port mapping 5899:5899 for Next.js, env var to NEXT_PUBLIC_API_URL

### Fixed
- [Frontend] Header.tsx: remove unsupported asChild prop from DropdownMenuTrigger (Base UI does not support Radix-style asChild)
- [Frontend] api-client.ts: cast empty response to T to satisfy strict TypeScript return type

### Removed
- [Frontend] Remove stale Vite scaffold files (vite.config.ts, index.html, src/, public/) — only Next.js config remains after scaffold migration
- [Frontend] Remove duplicate postcss.config.js (conflicted with postcss.config.mjs Tailwind v4 config)

### Added
- [Broker] EngineAdapter — wraps broker.Broker to satisfy engine.BrokerExecutor interface, enabling live trading engine to use any registered broker
- [Broker] FutuBroker — TCP connection to FutuOpenD gateway (default localhost:11111), JSON-encoded wire protocol with auto-reconnect (3 retries: 2s/5s/10s)
- [Market] BinanceFeed — WebSocket kline feed (wss://stream.binance.com:9443/ws), implements MarketFeed interface with Subscribe/Unsubscribe/auto-reconnect
- [Papertrade] Engine package — paper trade run management with state machine (created→running→paused→stopped→error), in-memory repository, CRUD operations
- [API] PaperTradingHandler refactored to delegate to papertrade.Engine package, removing inline pipeline/runner logic
- [Frontend] Add Dockerfile for Next.js production build (node:22-alpine multi-stage, port 5899)
- [Frontend] Add Vitest test infrastructure: vitest.config.ts with React plugin + jsdom + @/ alias, __tests__/setup.ts, 28 passing tests (utils + KpiCard)
- [Engine] OptionsEngine: US equity options trading with Black-Scholes pricing, per-contract commission, contract multiplier (100), short margin, and long/short PnL
- [Engine] FuturesBase: embeddable struct with shared futures contract calculations (RoundSize, CalcCommission, CalcMargin, CalcPnL, ApplySlippage, CanExecute)
- [Engine] ChinaFuturesEngine: CFFEX/SHFE/DCE/ZCE/INE/GFEX with 16 contracts (IF, IC, IH, RB, CU, AU, I, JM, C, CF, SR, TA, SC, NR, SI, LC), percentage-based commission
- [Engine] GlobalFuturesEngine: CME/ICE/EUREX with 8 contracts (ES, NQ, CL, GC, B, CC, FDAX, FESX), per-contract flat commission
- [Engine] ForexEngine: FX spot/CFD trading engine with pip-based PnL, margin (30:1 leverage), spread config, and zero commission
- [Engine] CompositeEngine: updated ForSymbol routing for all 7 engine types with priority-based symbol matching (A-share → futures → options → crypto → forex → global equity)
- [Broker] Broker interface with Binance (USDT-M Futures) and OKX (perpetual swaps) via native REST API
- [Broker] BrokerFactory with self-registration pattern, 13 mock-based tests
- [Market] MarketFeed interface + OKXFeed WebSocket implementation with auto-reconnection
- [Infra] Go core project scaffold with gin HTTP server and health endpoint
- [Market] Sina loader (P1): real-time A-share quotes from hq.sinajs.cn, text format, no API key
- [Market] Baidu loader (P6): historical A-share daily bars from Baidu Finance, JSON format, no API key
- [Market] TwelveData loader (P7): historical A-share daily bars with optional API key, string-value JSON parsing
- [Market] YFinance loader (P8): US/HK equities via Yahoo Finance v8 chart API, no API key
- [Market] CoinGecko loader (P12): 1000+ cryptocurrencies via public API, no API key
- [Market] GrpcDataLoader: bridges Python-only sources (mootdx) via gRPC DataService
- [Python] DataService gRPC server wrapping mootdx (通达信 TCP protocol) for Go consumption
- [Proto] data.proto: DataService.FetchBars for Python↔Go data bridge
- [Python] DataService: mootdx(P2), tushare(P3), futu(P4), akshare(P11) — 4 sources available via gRPC
- [Market] Cache interface and MemoryCache implementation with TTL support
- [Market] DataStore 3-tier fallback: cache → TimescaleDB → local store → loader registry (8 loaders across 4 markets)
- [Market] LocalStore: JSONL-based Tier 2 bar storage with timestamp dedup, exchange-organized directories
- [Engine] Core Engine interface with 6 methods (CanExecute, RoundSize, CalcCommission, ApplySlippage, CalcMargin, CalcPnL)
- [Engine] Domain types: Order, Position, Portfolio with validation and PnL calculations
- [Engine] OnBar pipeline with gap detection, suspension detection, signal processing, risk exits, OMS, and equity recording
- [Engine] RiskManager with stop-loss, take-profit, and trailing stop exit generation
- [Engine] GrpcSignalAdapter calling Python SignalService via gRPC (verified end-to-end)
- [Python] gRPC SignalService server with protobuf-to-DataFrame conversion, pluggable strategy
- [Python] gen_proto.py: proto generation script for Go↔Python shared protobuf definitions
- [Engine] ChinaAEngine with A-share rules: 万三 commission, 千一 stamp duty, minimum 5 yuan, 100-share round lot, 0.1% slippage
- [Engine] CompositeEngine with market-specific routing via symbol prefix
- [Engine] EngineFactory for registering and resolving engines by market type
- [Market] LocalStore stub for Parquet-based Tier 2 storage
- [Engine] BacktestRunner with multi-symbol bar alignment, equity curve, Sharpe/max-drawdown/win-rate metrics
- [Engine] LiveTradingRunner with goroutine-based event loop and start/stop control
- [Engine] NoopSignalAdapter for signal-free pipeline operation
- [API] POST /api/v1/backtest — run backtest with configurable symbols/date range/capital
- [API] GET /api/v1/backtest/:id — fetch backtest result
- [API] POST /api/v1/trading/start|stop — live trading control
- [API] GET /api/v1/trading/status — live trading status and portfolio
- [Infra] Protobuf definitions for 6 gRPC services (signal, factor, llm, analysis, workflow, common)
- [Infra] Buf-based code generation pipeline
- [Infra] Updated Docker Compose with go-core, python-research, frontend, postgres, redis services
- [Infra] CI/CD pipeline with Go lint+test+race and Python lint+test
- [CLAUDE.md] Spec → Plan → Test → Development Flow rule (development now requires spec + plan + tests before coding)

### Changed
- [Infra] Python code relocated from `backend/` to `services/python/`
- [Infra] Architecture documented as Go + Python hybrid in CLAUDE.md
- [Version] Updated to v2026.6.20

### Fixed
- [Engine] Pipeline: type assertion guard on bar, sorted bar window for deterministic signal generation
- [Engine] Pipeline: order validation and slippage applied in executeOrder
- [Engine] BacktestRunner: sorted symbol iteration for deterministic trade recording
- [Engine] BacktestRunner: commission included in trade records
- [Engine] BacktestRunner: std dev now uses sample variance (n-1 denominator), single-value edge case handled
- [Engine] Composite: guard against empty symbol in ForSymbol
- [Market] MemoryCache: maxEntries limit with 20% FIFO eviction to prevent unbounded growth
- [Market] MemoryCache: proto.Clone on GetBars to prevent shared mutation bugs
- [Market] EastMoney loader: BJ exchange (4/8/9 prefix) support via secID mapping, User-Agent header
- [Market] Tencent loader: User-Agent header, historical data guard
- [Market] Registry: dedup on Register to prevent duplicate loaders
- [DB] TimescaleDB: nil pool guard in InsertBars
- [API] Backtest handler: input validation (symbols, date range, cash, frequency)
- [API] Trading handler: deep copy portfolio to prevent race conditions
- [API] Auth middleware with API_KEY env var support
- [Server] Graceful shutdown with SIGINT/SIGTERM handling
- [Engine] ChinaAEngine: NewChinaAEngine() constructor replaces struct literal

### Removed
- [Infra] Old `backend/` directory (replaced by `services/python/`)

## [2026.6.14] - 2026-06-14

### 新增 — Visualizer 工作流节点
- **[Workflow] VisualizerNode** — 前端可视化节点组件，支持运行摘要图表的嵌入式展示
- **[Workflow] visualizer_nodes.py** — 后端可视化节点实现，提供数据可视化能力
- **[Workflow] i18n 条目** — 新增 visualizer 相关多语言 key（en/zh/ja/ko）
- **[Workflow] NodePalette 更新** — 注册 Visualizer 节点到调色板
- **[Workflow] RunSummaryPanel** — 运行摘要面板增强，集成图表展示

## [2026.6.10] - 2026-06-10

### 新增 — 文档与安全审计
- **[Docs] architecture.md** — Mermaid 架构图，覆盖系统分层、数据流、引擎管道、因子挖掘、部署拓扑
- **[Docs] getting-started.md** — 新手入门指南：Docker / 本地开发 / 测试 / 核心概念
- **[Docs] testing.md** — 测试指南：markers、隔离机制、CI 管道、编写规范
- **[CI] Dependabot** — pip / npm / GitHub Actions / Docker 四个生态系统自动依赖更新
- **[CI] security job** — pip-audit (Python) + npm audit (frontend) 在每次 push/PR 时扫描已知 CVE
- **[CI] test-fast depends on security** — 安全扫描不通过则阻止测试合并

### 修复
- **[Docs] CLAUDE.md 断链** — 移除指向不存在的 `13-核心缺陷分析.md` 的引用，改为指向 CHANGELOG.md

### 清理 — 过时文档归档
- **[Docs]** 将 3 份已实施的规划文档从 `docs/superpowers/plans/` 移至 `docs/archive/`：`ENHANCEMENT_PLAN.md`、`implementation-plan.md`、`2026-06-07-oled-trading-terminal.md`，并添加 `README.md` 说明
- **[Docs]** 创建 `docs/archive/optimization-suggestions.md` 占位文件，消除 `implementation-plan.md` 中的死引用
- **[Docs]** VERSION 和 README 版本号从 v2026.6.9 更新至 v2026.6.10

## [2026.6.9] - 2026-06-09

### 新增 — 工作流引擎增强（Phase 1-4）

#### Phase 1：基础能力
- **[Workflow] IF 条件节点增强** — 支持 AND/OR 多条件逻辑 + 8 种运算符（> >= < <= == != contains in）+ dot-path 字段解析，向后兼容单条件配置
- **[Workflow] SubWorkflowNode** — 子工作流嵌套执行节点，支持 workflow_id 加载或内联 JSON，输入/输出通过端口传递
- **[Workflow] 调试模式** — WorkflowEngine 新增 debug_mode + breakpoint 支持，可在指定节点暂停执行、查看中间数据、逐步推进

#### Phase 2：风控研究节点
- **[Workflow] VaRNode** — 历史模拟法 + 参数法 VaR/CVaR 计算，支持多置信区间 + 持有期缩放
- **[Workflow] StressTestNode** — 5 个历史压力场景（2015 股灾/2018 去杠杆/2020 熔断/2022 加息/2024 震荡），输出情景 P&L + 最大回撤 + 恢复天数
- **[Workflow] TurnoverNode** — 信号换手率分析，日/年化换手率 + 交易成本估算
- **[Workflow] FactorDecayNode** — 因子 IC 衰减曲线 + 半衰期估算，支持 Rank IC 和标准 IC
- **[Workflow] ParamHeatmapNode** — 2D 参数网格搜索 Sharpe 热力图

#### Phase 3：执行交付节点
- **[Workflow] PDFReportNode** — Jinja2 + WeasyPrint 生成专业级 PDF 报告，内置 default/compact 模板
- **[Workflow] PortfolioNode** — 多策略组合器，支持等权/风险平价/最小方差/最大 Sharpe 4 种分配方法
- **[Workflow] 历史回放 API** — `POST /runs/{run_id}/replay` 重新执行历史工作流

#### Phase 4：体验生态
- **[Workflow] 5 个预置模板** — 动量/均值回归/多因子/配对/因子挖掘完整 DAG 模板
- **[Workflow] 批量运行对比** — `POST /workflows/{id}/batch` 参数网格搜索 + 结果对比
- **[Workflow] 节点 I/O 预览** — `GET /runs/{run_id}/node/{id}/preview` 查看节点输入输出摘要
- **[Workflow] 导入/导出** — `POST /export` + `POST /import` JSON 格式工作流分享

#### 新增 PortType
- VAR_RESULT / STRESS_RESULT / TURNOVER_RESULT / DECAY_RESULT / HEATMAP_RESULT / PORTFOLIO_SIGNAL

#### 前端集成
- **[Frontend] 端口类型修复** — 新增 6 个 PortType 的 TypeScript 定义、Handle 颜色、Dot 颜色、中文标签，修复连接验证降级问题
- **[Frontend] 节点 i18n** — 8 个新节点的中英文翻译 + 6 个工具栏按钮翻译
- **[Frontend] 工具栏增强** — 新增 Export（下载 JSON）、Import（上传 JSON）、Batch（参数网格搜索）、Replay（历史回放）4 个按钮及完整面板 UI
- **[Frontend] 节点 Badge** — 8 个新节点的快速结果格式化（VaR 指标、压力场景数、换手率、半衰期、热力图网格、PDF 文件名、组合策略数）
- **[Frontend] RunSummaryPanel** — 8 个新节点图标 + formatSummary 指标展示
- **[Frontend] SubWorkflow 选择器** — 子工作流节点的 workflow_id 字段改为下拉选择器，自动加载当前项目的工作流列表
- **[Frontend] api.ts** — 新增 exportWorkflow, importWorkflow, batchRunWorkflow, replayRun, previewNodeRun, listPresets 6 个方法

### 修复
- **[Security] alpha_bench_tool 缓存改用 JSON 替代 pickle** — 移除 `pickle.loads/pickle.dumps`，改用 `json.dumps` + `DataFrame.to_dict/from_dict`，消除反序列化攻击面（P0-1）
- **[Security] background_tools shell=True 安全文档** — `shell=True` 已有 `shell_tools_enabled_for_request()` 访问控制，补充安全说明（P0-2）
- **[FactorMining] enhanced_fitness R² 计算修复** — `np.sum(residuals)` 在秩亏时返回空数组导致 R²=1.0，改为手动 `np.sum(residual**2)` 计算（P0-3）
- **[Auth] change_password 密码长度验证统一** — 从 4 位改为 8 位，与 register/reset 一致
- **[Auth] forgot-password token 泄露修复** — 仅 dev 模式（无 API_AUTH_KEY）返回 token 到响应体
- **[FactorKB] get_kb 单例线程安全** — 加 `threading.Lock` 双检锁
- **[DataStore] get_data_store 单例线程安全** — 加 `threading.Lock` 双检锁
- **[SignalAdapter] 频率推断修复** — 批量模式回退路径从 `Timedelta(days=1)` 改为 `pd.infer_freq()`，修复日内数据时间线错乱
- **[SignalAdapter] 条形记录一致性** — 与 engine.py `_record_bars()` 使用相同的频率推断逻辑
- **[StrategyLab] exec() 安全校验** — `_execute_strategy_code` 执行前调用 `validate_code_safety()`
- **[Engine] os.environ 中间件文档** — async 竞态限制说明，多用户部署建议 `--workers N`
- **[Engine] _active_symbol 并发文档** — 共享可变状态在并发场景的限制说明

### 变更
- **[Engine] 成交量滑点模型接通** — `_open_position`/`_close_position` 新增 `volume` 参数，A 股分级滑点（<50 万 0.3%/50-500 万 0.15%/>500 万 0.05%）正式启用
- **[Engine] 最小交易名义金额检查** — 新增 `TRADING_MIN_NOTIONAL`（默认 100），低于阈值的仓位不再开仓
- **[Logging] 96 个静默异常块添加日志** — 全局 `except Exception: pass` 替换为 `logger.debug()/warning()`
- **[Logging] 14 处 print("[WARN]") 替换** — `yfinance_loader/tushare/okx/base/ui_services` 改用 `logger.warning()`
- **[Config] DB_USER 默认值修正** — `pool.py/sse_bus.py` 从 `"shenzhiwei"` 改为 `"postgres"`
- **[API] FastAPI on_event 迁移至 lifespan** — 移除废弃的 `@app.on_event("startup")`，改用 `@asynccontextmanager` lifespan

### 新增
- **[Workflow] Phase 4: Templates, Batch, Preview, Import/Export** — complete workflow enhancement suite
  - **[Presets] 5 pipeline presets** — `momentum_strategy`, `mean_reversion_strategy`, `multi_factor_strategy`, `pair_trading_strategy`, `factor_mining_pipeline`; each returns a full `WorkflowModel` with wired nodes and edges
  - **[BatchRunner] Parameter grid execution** — `BatchRunner.run_batch()` generates all `itertools.product` combinations, clones workflow per combo, executes via `WorkflowEngine`, and builds metric comparison summary
  - **[API] Node I/O preview** — `GET /workflow/runs/{run_id}/node/{node_id}/preview` returns DataFrame shape/head/dtypes, dict keys/values, list items for debugging node outputs
  - **[API] Workflow export/import** — `POST /workflow/export` serialises workflow to JSON; `POST /workflow/import` validates node types against registry, checks port compatibility, and creates workflow in DB
  - **[API] Batch run endpoint** — `POST /workflow/workflows/{id}/batch` with `param_grid` body for parameter sensitivity analysis
  - **[API] Pipeline preset endpoints** — `GET /presets`, `GET /presets/{id}`, `POST /presets/{id}/instantiate`
- **[Workflow] isValidConnection 恢复** — 工作流画布连接类型校验重新启用，拖拽时即时阻止不兼容连接
- **[Template] 7 个策略模板生成器** — grid_trading/dca_buy/breakout_volume/mean_reversion_bb/turtle_trading/pairs_trading/momentum_rotation 从占位符改为可运行的骨架代码
- **[Skills] OKX API URL 常量化** — 新建 `skills/_constants.py`，30 处硬编码 URL 添加共享常量引用
- **[Config] MIN_NOTIONAL 配置** — `trading/config.py` 新增最小交易名义金额环境变量

## [2026.6.8] - 2026-06-08

### 修复
- **[GPEngine] `_random_tree_restricted` 内部节点构造错误** — 修正 `ExpressionTree(op=op, children=[child])` → `ExpressionTree(ExpressionNode(op=op, children=[child.root]))`，修复 TypeError
- **[Engine] Gap/暂停退出使用 `BaseEngine._close_position`** — 改为调用 `TradingEngine._close_position`，确保滑点应用和 `TradeRecord` 返回，修复 `BarResult.trades` 缺失
- **[WSFeed] 移除 `_recv_loop` 中死代码 `except Exception: raise`** — 无操作代码清理
- **[Tests] 新增 RiskPipeline、SignalAdapter、TradingEngine 核心路径测试** — gap 检测、日内止损、日亏损、批量模式 look-ahead 防护、_close_position/ _process_signals 等 56 个测试
- **[Correlation] 修复 Pandas 3.x `np.fill_diagonal` 只读数组崩溃** — `corr_df.values` → `corr_df.to_numpy(dtype=float, copy=True)`

## [2026.6.7] - 2026-06-07

### 新增
- **[Workflow] 输出节点结果可视化** — BaseNode NodeFooter 类型感知徽章（回测: Sharpe/Return, 评分: 等级, 通知: 通道状态等）+ RunSummaryPanel 运行摘要面板（执行后自动展示所有 output/analysis/execution 节点结果）
- **[Workflow] 5 个新节点** — FactorToStrategyNode（因子→策略一键生成）、StrategyHistoryNode（策略时间线+漂移检测）、SaveAsTemplateNode（工作流→模板）、CrowdingNode（因子拥挤度检测）、WalkForwardNode（锚定OOS验证）
- **[Notify] 可操作错误消息** — NotifyNode 增加 10 种常见错误的 action hint（含导航目标），error_action 字段输出到前端
- **[UX] 颜色一致性** — 28 个文件 43 处硬编码 text-emerald/text-red 替换为 i18n-aware text-up/text-down
- **[UX] NodePalette 频率排序** — 同分类内节点按使用次数降序排列，持久化到 localStorage

### 变更
- **[Engine] workflow_engine** — 优先使用节点提供的 `_summary` 字段（代替自动生成 DataFrame shape）
- **[Backend] BacktestNode** — 输出增加 `_summary`（sharpe/total_return/max_dd/trade_count）
- **[NodeRegistry]** — 新增 5 个节点类型

## [2026.6.6] - 2026-06-06 (Enhancement Plan Phase 0-7)

### 新增
- **[Cache] Redis L0 缓存层** — 新增 `src/cache/` 模块（redis_client 连接池 + data_cache OHLCV 缓存），Redis 不可用时优雅降级
- **[Notify] 多渠道通知** — Telegram Bot / Discord Webhook / Feishu 自定义机器人 + URL 方言自动检测。Alert 类扩展交易信号上下文字段
- **[Notify] NotifyNode + RiskPipeline 内联通知** — 工作流通知节点 + 止损/止盈触发自动告警
- **[Broker] 多券商扩展** — BaseBroker 抽象基类 + Binance/OKX 永续合约适配器（ccxt）+ BrokerNode 工作流节点 + CredentialStore 凭证加密
- **[Experiment] 实验管线** — StrategyScorer（7 维 Sigmoid 评分 A-E 级）+ VariantGenerator（grid/random 搜索）+ ExperimentNode/ScoreNode/RankSelectNode 三节点闭环
- **[Regime] 市场状态检测** — RegimeEngine（6 维特征规则型分类 + A 股特有状态）+ RegimeNode 工作流节点
- **[Evolution] 策略进化引擎** — StrategyEvolution（Grid→Perturb→Crossover→LLM→WalkForward 5 代迭代 + OOS 过拟合检测 + 早停）
- **[Reflection] AI 反思闭环** — ReflectionWorker（7 天后验证决策正确性）+ analysis_memory 表 + remember_analysis Agent 工具
- **[i18n] 日语/韩语** — ja/ko 翻译 + 浏览器语言自动检测
- **[DevOps] GitHub Actions** — docker-publish.yml（tag push → build → push ghcr.io）
- **[Tests] 3 个新测试文件** — test_strategy_scorer / test_variant_generator / test_broker_factory（19 个测试用例）

### 变更
- **[DataStore] Redis L0** — get_ohlcv/get_multi_ohlcv 新增 Redis 优先查询 + 自动回写
- **[Schema] 5 个新 PortType** — NOTIFY_CONFIG/ORDER_RESULT/REGIME_RESULT/EXPERIMENT_RESULT/SCORE_RESULT
- **[NodeRegistry] 3 个新节点模块** — notify_nodes/experiment_nodes/regime_nodes
- **[API] 4 个新路由端点** — notification test+list / experiment generate+score+detect-regime
- **[docker-compose] Redis 服务** — redis:7-alpine, 256MB, ALLKEYS-LRU
- **[requirements.txt] 新增 redis>=5.0.0**
- **[NodePalette] 3 个新图标** — Plug, Activity, Award

## [2026.6.6] - 2026-06-06

### 新增
- **[Workflow] 因子原子节点系统** — 新增 22 个可组合的原子因子节点（`factor_atoms.py` + `signal_nodes.py`），覆盖六层：数据提取（`column_extract`/`constant`）、变换（`ma`/`ema`/`delta`/`pct_change`/`std_dev`/`rank`/`scale`/`math_transform`）、运算（`arithmetic`/`extremum`）、滚动窗口（`rolling_extremum`/`rolling_rank`/`rolling_scale`/`rolling_correlation`）、逻辑判断（`cross_over`/`compare`/`bool_combine`/`bool_not`/`if_else`）、信号构造（`rank_select`/`threshold_select`/`signal_weight`/`rebalance`/`hold_signal`）。节点间通过 `DF_FACTOR`/`SIGNAL` 类型端口传递数据，连线即逻辑
- **[Workflow] 卡片内联参数编辑** — `BaseNode.tsx` 新增 `InlineParams` 组件，`config_schema` 中标记 `inline: true` 的字段直接渲染为卡片上的微型输入控件（数字框/下拉框），无需打开侧边栏即可修改关键参数（ComfyUI 风格）
- **[Workflow] L1: ExpressionTree→Workflow 自动转换** — 新增 `tree_converter.py`，将 AlphaZoo 的 400+ 因子自动转换为可视化节点 DAG。支持 24 种运算符映射（算术/截面/时序/条件），带分层布局算法。API: `POST /tree-to-workflow`
- **[Workflow] L2: 策略模板匹配** — 新增 `templates/registry.py`，8 个预置策略模板（单因子排名/双均线交叉/多因子复合/阈值突破/RSI均值回归/布林带/量价确认/动量轮动）。基于代码特征的模式匹配器（regex 规则），金叉策略匹配得分 1.0，未知策略不误匹配。API: `GET /templates`, `GET /templates/:id`, `POST /match-template`
- **[Workflow] L3: AI 策略拆解** — 新增 `strategy_decomposer.py`，将 Python SignalEngine 代码通过 LLM 分解为 workflow JSON。包含：51 节点 catalog 注入 System Prompt、JSON 提取（支持 code block/plain/mixed 三种格式）、结构校验（node_type 存在性/edge 节点引用）、最多 2 次自修正重试。API: `POST /decompose-strategy`, `GET /node-catalog`

### 变更
- **[Workflow] NodeRegistry** — 新注册 `factor_atoms`、`signal_nodes` 两个模块，总节点数 26→51
- **[Workflow] BaseNode** — 卡片最大宽度 240→280px 以容纳内联参数
- **[Workflow] CrossOverNode** — 新增 `direction` 参数（above/below），同时支持金叉和死叉检测
- **[Workflow] ArithmeticNode** — op 枚举扩展 `pow`（幂运算）
- **[Workflow] workflow_routes** — 新增 6 个 API 端点：`tree-to-workflow`、`templates`、`match-template`、`decompose-strategy`、`node-catalog`

### 修复（P0 全面审计）
- **[Engine] P0-1 佣金费率对齐** — `ChinaAEngine` 默认佣金率从万2.5（0.00025）修正为万3（0.0003），与 CLAUDE.md 记载和 CHANGELOG P0 修复记录一致。同时更新模块 docstring 和内联注释
- **[Workflow] P0-2 信号节点性能向量化** — `ThresholdSelectNode` 从 O(n³) 三重循环改为 pandas 向量化操作（`selected_mask.sum(axis=1)` + `.div()`），5000×500 数据集执行时间从 >10s 降至 <0.1s。`RankSelectNode` 改用 `DataFrame.rank(axis=1, method="first")` 单次排序替代逐行循环。`SignalWeightNode` equal/factor_proportional 两种模式均改为 DataFrame 向量化（`fillna(0) + (df!=0).sum(axis=1) + .div()`）。`HoldSignalNode` 用 `cummax()` / `cumsum()` 向量化替代逐 code×逐 date Python 循环
- **[Security] P0-3 工作流路由脱敏** — `workflow_routes.py` 中 8 处 `detail=str(e)` 替换为通用错误消息，防止内部异常信息泄露。同步修复 `tree-to-workflow` 端点区分 ValueError（400 客户端错误，可透传消息）与通用异常（500 通用消息）
- **[Frontend] P0-5 测试覆盖补全** — 新增 3 个测试文件：`workflowTypes.test.ts`（PortType 枚举 + isCompatible 兼容性矩阵）、`authStore.test.ts`（token 恢复/注销/损坏数据处理/登录错误）、`workflowStore.test.ts`（节点 CRUD/连线验证/脏状态/执行日志）。修复 `apiAuth.test.ts` 中 sessionStorage vs localStorage 不一致（auth store 已改用 sessionStorage）。修复 `auth.ts` 中损坏 JSON 时未清除状态的问题

### 修复（P1 深度优化）
- **[Workflow] P1-5 _to_factor_df 去重** — `factor_atoms.py` 和 `signal_nodes.py` 中重复的 14 行 `_to_factor_df` 函数提取到共享模块 `nodes/_utils.py`，统一导出为 `to_factor_df`。两处分别 `import ... as _to_factor_df` 保持接口向后兼容
- **[Engine] P1-6 精确异常捕获** — `TradingEngine._process_signals()` 中 `except Exception:` 替换为 `except (ValueError, KeyError, TypeError, AttributeError, IndexError) as e:`，防止 `KeyboardInterrupt` 和 `SystemExit` 被吞没
- **[GP] P1-7 Docstring 修正** — `gp_engine.py` 模块 docstring 中 FDR 校正方法从 `Benjamini-Hochberg` 修正为 `Benjamini-Yekutieli`（BY），与代码实际调用 `apply_by_correction()` 一致
- **[Workflow] P1-9 信号节点测试** — 新增 `test_signal_nodes.py`（21 个测试），覆盖 `RankSelectNode`（top_n/升序/超额 top_n）、`ThresholdSelectNode`（gt/lt/gte/无匹配）、`SignalWeightNode`（equal/factor_proportional/空信号）、`HoldSignalNode`（进入/退出/初始 long/多股票）、`RebalanceNode`（持有/频率=1 透传）、因子管线端到端集成测试、CPU 进程池冒烟测试
- **[Workflow] P1-2 画布 Undo/Redo** — `workflowStore` 新增历史栈（最多 50 步）：`addNode`/`removeNode`/`updateNodeConfig`/`onConnect` 操作前自动快照，`undo()`/`redo()` 恢复。`WorkflowCanvas` 添加键盘快捷键 Ctrl+Z（撤销）、Ctrl+Shift+Z / Ctrl+Y（重做）
- **[Workflow] P1-3 节点搜索** — `NodePalette` 已内置搜索功能（按标签/描述/node_type 过滤），无需额外修改

### 修复（P2 质量提升）
- **[Workflow] P2-17 延迟 CPU 池初始化** — `workflow_engine.py` 中模块级 `_CPU_POOL = ProcessPoolExecutor(...)` 替换为延迟初始化 `_get_cpu_pool()`，避免在 ASGI 非主线程导入时创建进程池。首次调用时创建，线程安全
- **[Workflow] P2-14 策略拆解器测试** — 新增 `test_strategy_decomposer.py`（21 个测试），覆盖 `_extract_workflow_json` 9 种格式（纯 JSON/代码块/混合文本/无效输入/空响应）、`_validate_workflow` 6 种场景（合法/缺 ID/未知类型/边引用未知节点/无节点/完整管线）、`get_node_catalog` 结构验证
- **[Workflow] P2-13 画布复制粘贴** — `workflowStore` 新增 `copySelectedNode()`/`pasteNode()`/`hasClipboard()` 操作。`WorkflowCanvas` 添加 Ctrl+C（复制选中节点）、Ctrl+V（粘贴到画布中心）快捷键。复制时不干扰文本选择
- **[API] P2-16 错误码标准化** — 新增 `src/api/error_codes.py`：`ErrorCode` 枚举（20 个机器可读错误码）+ `api_error()` 工厂函数 + 默认 HTTP 状态映射 + `internal_error()`/`not_found()` 快捷函数。所有错误响应格式统一为 `{"error_code": "...", "message": "..."}`
- **[Workflow] P2-15 演示工作流** — 新增 3 个初学者友好的演示模板（`demo_momentum` 动量策略/`demo_macross` 均线交叉/`demo_volbreak` 成交量突破），带完整节点+边预置，通过 `POST /templates/{id}/instantiate` 一键创建

### 修复（P3 收尾优化）
- **[Trading] P3-21 魔术数字配置化** — 新增 `src/trading/config.py`：集中管理 `MAX_HISTORY`、`EPSILON`、`DEFAULT_NODE_TIMEOUT`、`MAX_CONCURRENCY`、`RESOURCE_LIMITS`、`GP_POPULATION_SIZE` 等 15+ 个可调参数。所有值支持环境变量覆盖（如 `TRADING_MAX_HISTORY`）。`signal_adapter.py` 和 `engine.py` 改为从 config 导入
- **[Frontend] P3-20 空状态设计统一** — 新增 `EmptyState` 共享组件（支持 icon/title/description/action，sm/lg 尺寸变体）。`Projects` 页面已接入，其余页面渐进迁移
- **[Frontend] P3-19 参数网格搜索 UI** — 新增 `GridSearch` 组件（`components/strategy-lab/GridSearch.tsx`）：选择 1–2 个参数定义范围+步长 → 笛卡尔积生成全量组合 → 并发执行回测（batch=3）→ 按 Sharpe 排名表格展示。可嵌入 StrategyLab 等回测页面
- **[Engine] P1-6 异常捕获补充** — `_process_signals` 异常类型补充 `RuntimeError`，兼容 `can_execute` 等市场规则检查可能抛出的运行时异常

### 修复
- **[Workflow] 回测结果与策略实验室不一致** — 三个根因：① strategy_code 路径实例化 SignalEngine 失败回退至 StaticSignalEngine（存在前瞻偏差）；删除 strategy_code 端口，只用 signal 模式（BacktestDriver._run_fast 已有逐根 K 线截断防前瞻）。② BacktestNode 未输出 equity_curve，ChartDataNode 退化为买入持有近似值；现从 engine.equity_snapshots 提取真实权益曲线。③ BacktestNode._mk_engine 仅覆盖 4 种市场且硬编码 bars_per_year；改用 _create_market_engine 和 calc_bars_per_year 与策略实验室对齐
- **[Workflow] BacktestNode 初始资金与策略实验室不一致** — 统一默认 1,000,000（策略实验室从 100,000 → 1,000,000）
- **[Workflow] 回测交易记录只有入场没有出场** — 改为入场+出场配对输出，出场记录含 exit_time、exit_price、exit_reason、pnl
- **[Workflow] ChartDataNode 权益曲线用"T0,T1"假时间戳** — 改用 equity_snapshots 真实时间戳
- **[Strategy] 策略实验室 initial_cash 默认值从 100,000 改为 1,000,000** — 与 BacktestNode 对齐
- **[Workflow] 路由双 /v1 前缀导致 /projects 页面空白** — workflow_routes.py prefix 从 `/v1/workflow` 改为 `/workflow`
- **[Workflow] CSS @keyframes fade-in-up 缺失导致页面内容不可见** — 所有使用 page-enter-stagger 的页面内容卡在 opacity:0
- **[Workflow] 前端 dist 文件残缺导致所有页面白屏** — Docker 构建缓存问题，旧 index.html 引用已删除的 JS chunk
- **[Workflow] 节点连线死锁** — 同源→同目标多条线时依赖计数重复（strategy→backtest 的 signal + strategy_code）
- **[Workflow] 硬编码英文标签** — BaseNode.tsx 画布节点和 NodePanel 直接使用后端 label，改为 i18n 翻译
- **[Workflow] 图标名当文本渲染** — 后端 icon 字段（Lucide 名称）未映射为图标组件，显示裸文本
- **[Workflow] 节点 handle 连接困难** — 加大 handle 尺寸、增加吸附半径 connectionRadius=30
- **[Workflow] backtest_driver sys.exit(1) 炸掉进程池** — 改为 return error dict，不杀进程
- **[Workflow] BacktestNode 缺 start_date/end_date** — 导致 InMemoryLoader 日期查询失败
- **[Workflow] save_node_results DataFrame/Timestamp JSON 序列化报错** — 添加 _sanitize_for_json 递归转换
- **[Workflow] WorkflowRun 缺 created_at 字段** — schema.py 补充字段 + to_dict/from_dict
- **[Workflow] SSE 事件路径错误** — /v1/api/workflow → /v1/workflow
- **[Workflow] 过期锁不释放** — 添加 stale lock 自动检测
- **[工作流] 回测结果实时展示** — pollRun 轮询 + ECharts K线/权益/交易明细/指标面板
- **[策略] 保存策略空名称** — 自动从 class 名提取，fallback 带时间戳
- **[策略] 策略列表缺失 code 列** — pg_repository list_strategies SQL 补上 code 字段
- **[策略] Template 模板实例化 405** — 添加 POST /templates/{id}/instantiate 路由

### 新增
- **[Workflow] 策略节点 Saved 模式** — 从 Strategy Lab 选取已保存策略，支持 Template/Saved/Custom 三种来源
- **[Workflow] 回测节点渐进式执行** — 新增 strategy_code 输入口，逐根 K 线生成信号防未来信息
- **[Workflow] 回测节点 Slippage 配置** — 新增滑点（bps）配置项
- **[Workflow] 节点面板 Delete Node 按钮** — 选中节点可直接删除
- **[前端] 返回工作流按钮** — Full Editor 跳转后顶部显示 ← Back to Workflow
- **[前端] WorkflowChartViewer** — ECharts 渲染 K线/权益曲线/交易明细/指标面板

## [2026.6.4] - 2026-06-04

### 新增

- **[Workflow] 15 个新节点，节点总数从 11 → 26**
  - **计算节点（10）**：`IndicatorNode`（技术指标计算）、`CorrelationNode`（相关性矩阵）、`ComparisonNode`（策略对比统计检验）、`GPEvolutionNode`（GP 进化因子挖掘）、`NewsSentimentNode`（新闻情绪评分）、`MacroSentimentNode`（宏观情绪指标）、`OrderNode`（下单/撤单）、`FundamentalsNode`（基本面数据拉取）、`OptionsNode`（期权定价与希腊字母）、`SectorMapNode`（行业分类）
  - **Output 节点（5）**：`ReportGeneratorNode`（结构化报告 Markdown/JSON/Text）、`NotifyNode`（Webhook/邮件/控制台通知）、`ExportNode`（CSV/JSON/Parquet 导出）、`ChartDataNode`（前端 ECharts 图表数据：K 线、权益曲线、交易标记、指标面板）、`FactorPersistNode`（因子入库，formula_hash 自动去重，可选晋升 Alpha Zoo）
  - 新增 `PortType`：TECHNICAL_INDICATOR、CORRELATION_MATRIX、SENTIMENT、COMPARISON_RESULT

- **[Workflow] Output 节点完整覆盖因子管线**
  - `FactorPersistNode`：FactorKB 注册（SHA256 去重）→ Auto-Promote Top-N → Registry 动态注册（`register_dynamic()`），Alpha Zoo 立即可搜索，无需重启
  - `ChartDataNode`：汇总回测+行情+指标数据，产出前端 CandlestickChart/EquityChart 兼容的 JSON

- **[Workflow] 架构修复（P0-P3）**
  - **P0**：SSE 实时进度队列桥接引擎 → 前端（之前断裂）、`stop_workflow` 真正 cancel asyncio Task、CPU 节点通过 `ProcessPoolExecutor`（8 workers）并行执行，不再阻塞 event loop
  - **P1**：画布 Delete 键清理孤立边（`onNodesDelete` → `removeNode`）、`runSingleNode` 收集上游输入传 body、Run 前 auto-save（`isDirty` 检测）、删除重复路由定义
  - **P2**：节点超时机制（默认 600s + `timeout_seconds` 属性）、SSE endpoint 鉴权（`require_auth`）
  - **P3**：BaseNode 生命周期钩子（`on_init`/`on_validate`/`on_cleanup`/`on_cancel` + `version` 字段）、`_profile_sems` 竞态锁修复

- **[Workflow] AgentNode 增强**
  - 上游数据**结构化上下文注入**：自动检测 PortType（BACKTEST_RESULT → 指标表格、FACTOR_RESULT → 因子列表、CORRELATION_MATRIX → 摘要统计、COMPARISON_RESULT → 胜者分析等），非原始 dump
  - **Prompt 模板**：`{prompt}` 和 `{context}` 占位符，用户可自定义模板
  - 直接 config 输入 prompt（ChatInput 节点变为可选）

- **[Workflow] OHLCVLoaderNode 增强**
  - 新增 `source` 下拉选择 14 种数据源（auto/mootdx/tushare/eastmoney/tencent/futu/baidu/yfinance/twelvedata/finnhub/akshare/okx/ccxt/coingecko）+ `force_refresh` 开关

- **[Workflow] PaperTradingNode 增强**
  - 从纯校验 stub 改为可选「模拟交易」模式，真正调用 `LiveDriver` 运行 TradingEngine 逐笔管线，输出 equity/sharpe/max_drawdown

- **[Workflow] AttributionNode 增强**
  - 从 thin stub 改为调用 `AttributionEngine`：Brinson 分解、因子归因、行业归因、TCA

- **[Workflow] 修复 /projects 页面空白 — 路由双 `/v1` 前缀**
  - `workflow_routes.py` 的 `APIRouter(prefix="/v1/workflow")` 与 `api_server.py` 的 `v1` APIRouter(`prefix="/v1"`) 叠加，导致实际路由变为 `/v1/v1/workflow/projects`，前端请求 `/v1/workflow/projects` 匹配不上 → SPA fallback 返回 HTML → 空白页
  - 修复：去掉子 router 中多余的 `/v1`，统一为 `prefix="/workflow"`

- **[前端] 侧边栏恢复 Dashboard 入口**
  - `/` 路由从 Projects 改为 Dashboard，`/projects` 保持独立
  - Dashboard 全面重构样式（`section-card rounded-2xl`、hover 过渡）
  - Quick Navigation 精简为侧边栏匹配项 + Workflow 快捷入口
  - 侧边栏新增 Dashboard（LayoutDashboard），Projects 改用 FolderOpen

- **[前端] Workflow 画布 i18n 全覆盖**
  - 26 个节点 label + description + 9 个分类 + 15 个 UI 字符串中英文翻译
  - NodePalette/NodePanel 自动切换，翻译键 `wfNode_{type}` / `wfCat_{category}`

- **[前端] StockInput 集成进 Workflow**
  - NodePanel 支持 `stock_codes` / `stock_code` 自定义字段类型
  - StockUniverseNode custom_codes 改用搜索补全组件（替换纯文本框）

- **[Dashboard] 活动事件接入 Workflow**
  - Workflow 启动/完成/失败时写入 Dashboard activity log
  - 自动 60s 刷新，配合模拟盘和因子挖掘事件

### 变更

- **[前端] 全局 UI 重构 —「精准金融界面」设计语言**
  - 正文字体 Inter → DM Sans，品牌色调整，表面层级 2→4 级，新增强调色令牌
  - 按钮 rounded-lg 流畅过渡，卡片 rounded-xl + hover 微上浮，新增 6 个组件类
  - 4 个关键帧动画，页面交错入场，骨架屏渐变闪烁
  - 侧边栏贴边锚定，导航项 2px 左侧色条指示器
  - 测试：92 个通过（76 + 16 新增）

- **[工作流] 第四阶段：以项目为中心的导航 + 全编辑器集成**
  - 侧边栏简化为 Projects、Agent、Settings；/ 重定向到 Projects 页面
  - Projects 页面：项目卡片含工作流数量、创建/归档、一键打开
  - NodePanel「全编辑器」按钮：每个节点类型链接到对应旧页面
  - 旧路由保留以保证向后兼容；主要导航通过画布进行

- **[工作流] 第五阶段：模板、调度、版本历史、清理**
  - 模板、定时工作流运行、版本历史（快照 + 恢复）、冷数据清理
  - SchedulerEngine 现支持 `task_type="workflow_run"` — cron 触发器自动执行工作流

- **[工作流] 架构精简（减法重构）**
  - **删除**：`shared_storage.py`、`templates.py`、`execution_nodes.py`、`filter_nodes.py`、`deploy_nodes.py` — 5 个文件
  - **删除节点**：SubWorkflow、Merge、Loop、ParameterScan — 4 个占位节点移除
  - **合并**：BacktestNode → `strategy_nodes.py`；ScreenerNode + PaperTradingNode → `thin_nodes.py`
  - **schema.py**：移除 DataArtifactRef 类；PortType 从 3 段字符串简化为扁平枚举；同类型或通配符兼容
  - **node_base.py**：移除 @dataclass；干净的类级别属性继承
  - **node_registry.py**：显式 `init_workflow_nodes()` 替代自动发现；在 API 服务器启动时调用
  - **workflow_engine.py**：移除 SharedStorage；`_reset()` 清除每次运行的状态；节点在内存中直接传递 DataFrame
  - **P0 修复**：启动时节点注册（init_workflow_nodes）、Scheduler 处理 workflow_run、InMemoryLoader 基于时间戳的日期过滤
  - **P1 修复**：运行间引擎状态重置、AgentNode run_dir 代码提取
  - **前端**：简化类型（PortType 枚举），移除 DataArtifactRef/ActionRef 类型，内联 Viewport 类型
  - 结果：后端约 1500 行（原约 2500 行，-40%），前端工作流约 900 行（原约 1500 行，-40%），9 个文件（原 20 个，-55%）
  - 60 个后端测试通过，12 个前端测试通过，零新增 TS 错误

## 2026.6.3 — P0-P3 深度审计 + 文档 + 测试修复

### 修复

- **[引擎] P0 前瞻性偏差回归修复** — `TradingEngine._record_bars()` 必须在 `_generate_signals()` 之后执行，防止策略通过 `_data_map` 访问当前 bar；`equity_for_sizing` 必须在风险检查前缓存，避免 `_last_bar_prices` 被今日收盘价更新后用于 sizing 计算
- **[引擎] P0 跳空检测漏单** — `RiskPipeline.check_gap()` 现在对开盘价穿透止损/止盈价的情况正确触发退出，之前仅对收盘价检查导致跳空止损完全失效
- **[GP] P0 排名确定性** — GP 锦标赛选择改用稳定排序（先按 fitness 降序，再按 `formula_hash` 字典序），消除同分个体的非确定性 shuffle
- **[引擎] P0 佣金费率修正** — A 股佣金从 0.3 bps 修正为 3 bps（万三），之前少算一个数量级导致回测收益虚高
- **[引擎] P1 列对齐错误** — `np.where()` 配合 `.values` 使用会丢失列标签，引入 `_safe_if_else()` 辅助函数替代，修复并行评估中 DataFrame 列混乱
- **[因子知识库] P1 pgvector 降级处理** — `factor_kb_store.py` 在 PostgreSQL 不可用时优雅降级为本地 JSON 存储，不再抛异常中断整个因子挖掘流程
- **[引擎] P1 日内时间戳推断** — bar 间隔计算从 `Timedelta(days=1)` 硬编码改为 `pd.infer_freq()` 动态推断，修复周线/4 周线/2 小时线等非日线周期的年化系数错误
- **[GP] P0 线程安全** — 并行 GP 评估中所有 KB 访问必须持有 `self._kb_lock`，修复 `factor_kb.register()` 并发写入导致的 SQLite 数据库锁竞争和数据损坏
- **[GP] P0 KB 溯源校验** — 复用 KB 中缓存的因子指标前必须校验 `data_source_version` 和 `train_date_range`，防止不同数据集/时间范围的指标被错误复用
- **[GP] P1 FDR 校正方法** — 多重假设检验校正从 Benjamini-Hochberg (BH) 改为 Benjamini-Yekutieli (BY)，因 GP 候选因子高度相关，BH 的独立性假设不成立
- **[GP] P1 OOS 评估窗口** — Walk-forward 窗口从重叠滑动改为非重叠滚动窗口，确保各窗口 OOS IC 相互独立，消除自相关导致的显著性虚高
- **[GP] P1 Elite Tracker 哈希** — Elite 个体追踪器改用 `formula_hash` 而非对象 id，修复重启后 tracker 无法识别同一公式的问题
- **[安全] P1 SIGALRM 替代** — `SafetyValidator` 的运行时断路器从 `signal.SIGALRM` 改为 `threading.Thread + join(timeout)`，SIGALRM 仅在 Unix 主线程可用，子线程中会静默失效
- **[数据] P1 加载器可用性检测** — `is_available()` 必须执行真实网络连通性检查，不能仅 `import requests` 就返回 True，修复离线环境下 loader 误报可用
- **[引擎] P1 退市检测** — `BacktestDriver` 检测到标的 K 线数据提前终止时触发 `force_close_symbol(code, "delisted")`，修复退市股票在回测中永远持有到最后的问题
- **[数据] P2 截断阈值** — Baidu loader 截断检测阈值从固定 2000 bar 改为动态计算（预期 bar 数的 95%），消除不同频率下的误报/漏报
- **[指标] P2 Scale NaN** — `calc_metrics()` 在全部收益为零时 scale 计算产生 NaN，添加 `np.where` 保护返回 0.0
- **[引擎] P2 预热期** — 回测指标计算跳过前 N 个 bar 的预热期（默认 21 交易日），避免初始空仓期污染夏普/最大回撤等统计量
- **[指标] P2 年化系数** — `calc_bars_per_year()` 补齐所有 interval 的年化系数映射（1W→52, 4W→13, 2d→126, 2h→756），修复非日线回测指标年化错误
- **[因子知识库] P3 主题归一化** — KB 主题标签从自由文本改为小写归一化 + 去重，修复同一主题因大小写/空格变体被识别为不同主题的问题
- **[测试] MockSignalAdapter 签名更新** — `on_bar_batch()` 增加 `*, skip_append=False` 参数以匹配 `SignalAdapter` 生产代码签名的变更，修复 4 个测试用例的 `TypeError`

### 新增

- **[文档] CLAUDE.md** — 项目开发指南：架构总览（TradingEngine 管道 / Backtest 引擎继承体系 / 数据加载 3 层架构 / 因子挖掘系统 / 前端状态管理 / Skills 系统）、构建/测试/运行命令、已知缺陷模式（8 类避免引入的 bug 模式）
- **[文档] 核心代码文档** — 9 个关键文件新增 1025+ 行 docstring（模块级/类级/方法级），覆盖安全边界/金融计算/数据完整性/并发/算法复杂度 5 类关键代码
- **[文档] 开发规则** — CLAUDE.md 新增 Changelog 维护规范（每次改动必须记录，Keep a Changelog 格式）和文档要求（5 类关键代码必须携带完整文档）
- **[基础设施] Docker 数据卷** — `docker-compose.yml` 新增 `/opt/data` 卷挂载，持久化 PostgreSQL 数据

### 变更

- **[文档] CHANGELOG.md** — 按 CLAUDE.md 规范新增 `2026.6.3` 条目，详细记录 5 轮 P0-P3 缺陷修复

## 2026.6.1 — C 阶段：LLM+GP+因子知识库三位一体 Alpha 工厂

### 新增

- **C 阶段：LLM + GP + FactorKB 三位一体 Alpha 工厂** — 完整实施计划 + 核心代码
  - `ExpressionTree` 作为唯一数据源：`formula_hash` (SHA256)、`normalized_formula`、`to_signalengine_code()`、`to_callable()` 均从同一棵树派生
  - 27 个算子，3 级渐进式解锁（basic/advanced/alternative），防止搜索空间爆炸
  - `enhanced_fitness.py`：乘法复合适应度 — `rank_ic × cost_penalty × orthogonality_penalty × a_share_penalty × stability × complexity_discount`
  - A 股专项惩罚：T+1 日内 ×0.5、极端换手率 >200x ×0.3、小盘极端暴露 ×0.7
  - FDR 多重检验校正（Benjamini-Hochberg, q=0.05），每代应用
  - `hybrid_init.py`：基于骨架的种群初始化（30% 已知有效结构 + 40% 变异 + 30% 随机），含 10 个 A 股因子骨架
  - `factor_kb.py`：FactorKnowledgeBase — 按 formula_hash 注册/查询/去重，生命周期状态机（discovered→validating→approved→paper_trading→production→deprecated→archived），语义标签搜索，主题健康分析的挖掘指导
  - `llm_intervention.py`：LLM 引导进化，7 种干预动作（inject_seeds/adjust_mutation/theme_redirect/avoid_redundant/no_op/…），结构化提示词含 few-shot 示例 + KB 上下文 + Zoo 反馈
  - 消融研究框架：3 组对照实验（Baseline/LLM/Placebo），Welch's t-test 验证 LLM 的真实贡献
  - `duckdb_evaluator.py`：DuckDB 基准门禁 — 10 个典型因子基准测试，仅在 >5x 加速时迁移
  - `safety_validator.py`：3 层防护 — AST 白名单验证器 + 类型签名验证器 + 运行时断路器（512MB/30s）
  - Walk-Forward 24 窗口清除交叉验证，5 天清除期
  - PAPER_TRADING 晋级门禁：≥21 交易日、Sharpe>0.5、换手率差距<1.5x、正收益、滑点<15bps
  - `factor_tools.py`：4 个 MCP 工具（factor_kb_search / factor_review / factor_mining_start_gp / factor_kb_list）+ 自动晋级管道
  - PostgreSQL DDL：7 张表（vt_factor_knowledge + snapshots + similarities + regime_performance + subtree_cache + archive + activity_log）
  - `factor_kb_store.py`：pgvector 语义搜索适配器，支持 PostgreSQL 优雅降级
  - `dashboard_routes.py`：C4 仪表盘聚合 API — 8 个模块并行，5s 超时，每模块优雅降级

- **数据源修复** — 免费 A 股数据可靠性全面升级
  - Runner 回退逻辑：现当数据未覆盖请求的日期范围时触发（不仅限于数据为空时）
  - `_data_covers_range()` 辅助函数，60 天容差用于覆盖缺口检测
  - `mootdx_loader.py`：已分页（800 bar 块，循环直到覆盖），TDX 免费服务器限制已文档化
  - `eastmoney.py`：新增 `_fetch_one_paginated()` — 基于日期的分页，使用 `end` 参数，300 bar 块，500 块安全上限
  - `baidu.py`：新增截断检测，服务器截断数据未覆盖请求范围时发出警告
  - 系统提示词 + strategy-generate 技能：完整数据源历史深度指南（mootdx ~2-3年、eastmoney ~10年+、tencent ~10年+ 等）
  - `pyarrow>=14.0.0` 加入依赖，用于 Parquet 存储支持

### 变更

- **GP 引擎 P0 升级**（`gp_engine.py`）
  - `_evaluate_individual()`：从加法 `evaluate_fitness()` 切换为乘法 `composite_fitness()`，含与 KB 核心因子的正交性检查
  - `initialize_population()`：从纯随机切换为 `hybrid_initialize_population()`，自动提取 Zoo 幸存者作为额外骨架
  - FactorKB 自动注册：每代前 5 名显著个体自动注册到 KB，含公式去重
  - FDR 校正每代应用（原：仅对最终前 10 名应用）
  - 分级算子解锁：`evolve()` 现接受 `generation` 参数，变异按算子等级过滤
  - `GPEvolutionConfig`：7 个新字段（fitness_metric="composite"、use_tiered_operators、use_hybrid_init、skeleton_ratio、mutant_ratio、use_kb、fdr_alpha）
  - KB 挖掘指导每 10 代通过 SSE 推送
  - `GPEvolution.__init__()`：接受可选 `kb` 参数，自动加载核心因子用于正交性检查

- **ExpressionTree 增强**（`expression_tree.py`）
  - `formula_hash` 属性：规范化公式的 SHA256，用于去重
  - `normalized_formula` 属性：确定性形式，含交换算子排序、小写特征名、固定窗口编码
  - `to_signalengine_code()`：编译树 → 可部署的 SignalEngine Python 类
  - `OPERATOR_TIERS` 字典 + `get_allowed_operators()`：按代际进度渐进式解锁算子
  - `_normalize_node()` + `_compile_to_signalengine()`：规范化形式生成和代码编译辅助函数

### 测试覆盖
- `test_formula_consistency.py`：30 个测试，覆盖树→哈希一致性、序列化往返、SignalEngine 代码执行、KB 去重、生命周期状态机、混合初始化、增强适应度、算子等级和跨表示执行一致性
- 所有现有 976+ 测试通过

## 2026.6.1 — AI 因子挖掘引擎 + 股票筛选器 + 更多

### 新增

- **AI 因子挖掘引擎** — 遗传规划 + LLM 引导 Alpha 发现
  - 表达式树进化：20+ 算子，锦标赛选择，交叉/变异，复杂度惩罚（AIC/BIC）
  - Walk-Forward 验证：滚动 OOS 窗口替代简单训练/测试分割；适应度 = mean(OOS IC) − w·std(OOS IC)
  - Benjamini-Hochberg 多重检验校正；每个候选因子含 `adjusted_p_value` 和 `is_statistically_significant`
  - LLM 因子提取：PDF 研究论文 → 因子公式，通过结构化 JSON Schema 输出
  - 多 LLM 辩论过滤：3 个角色（quant/research/PM）独立评分候选因子
  - 混合 GP+LLM 协同进化：LLM 约每 5 代审查种群，建议搜索方向
  - 因子晋级：自动生成 `__alpha_meta__` + `compute(panel)` 代码到 `zoo/mined/`
  - SSE 实时进化图表：每代 IC 曲线，表达式树查看器
  - 13 个 API 端点 + 4 个前端组件（EvolutionChart、ExpressionTreeViewer、CandidatesTable、MiningProgressCard）
  - 数据库：`vt_factor_mining_runs`、`vt_factor_mining_candidates`

- **智能股票筛选器** — 450+ Alpha Zoo 因子 + 11 个技术指标的多条件过滤
  - 白名单验证：所有字段名和算子对照严格 frozenset 白名单验证
  - 参数化 SQL：`%s` 占位符防注入；`statement_timeout` 保护
  - 基于最近因子 IC 排名的 AI 推荐预设
  - 批量操作：加入自选、导出 CSV、等权篮子回测
  - 8 个 API 端点 + 数据库：`vt_screener_presets`、`vt_screener_runs`、`vt_screener_results`

- **策略统计对比** — 配对 t 检验、Bootstrap Sharpe CI（10k 样本）、White's Reality Check、CAPM/FF3 回归
  - 滚动窗口 Sharpe 稳定性分析
  - 叠加权益曲线端点
  - 3 个 API 端点 via `compare_routes.py`

- **业绩归因仪表盘** — Brinson（配置/选择/交互）、因子横截面回归、板块（申万分类）、时间序列分解
  - 聚合所有 4 个维度的完整归因报告端点
  - 5 个 API 端点 + 4 个前端图表组件

- **定时任务引擎** — 6 种任务类型：auto_backtest、data_health_check、watchlist_alert、signal_report、factor_mining、screener_run
  - 可视化 cron 构建器，含下次运行预览
  - 执行历史 + 日志查看器
  - PostgreSQL 持久化 + 通知集成
  - 9 个 API 端点 + 数据库：`vt_scheduled_tasks`、`vt_scheduled_task_executions`

- **新闻情绪分析** — 中文 NLP 情绪（SnowNLP）、个股级别聚合、热门话题、市场情绪概览（VIX/DXY/yield/F&G）
  - 独立 `/sentiment` 页面：热门话题排名含情绪条、市场情绪仪表卡片、实时新闻推送含 SSE
  - 增强 Trading 页面新闻 tab：每篇文章情绪评分徽章、个股情绪摘要栏、实时 SSE 更新
  - 通过 PostgreSQL LISTEN/NOTIFY 跨 worker 总线（SSEBus）实时 SSE 新闻流；可按标的或全市场订阅
  - 基于关键词的中文财经新闻话题提取（10 个话题类别）
  - `SentimentAnalyzer` 接入所有新闻端点；来自 DuckDuckGo/Finnhub 的真实新闻实时评分
  - 5 个 API 端点：`/news/feed`、`/news/sentiment/{symbol}`、`/news/trending`、`/news/market-sentiment`、`/news/stream`

- **策略版本控制** — 自动版本化，含统一 diff、版本对比、一键回滚
  - Diff 查看器组件，含 ± 语法着色
  - 5 个 API 端点 + 数据库：`vt_strategy_versions`

- **策略市场** — 发布/浏览/评分/安装策略
  - 5 星评分、安装次数排名、市场/类别过滤
  - 6 个 API 端点 + 数据库：`vt_strategy_marketplace`、`vt_strategy_ratings`

- **期权分析模块** — Black-Scholes 定价含完整希腊字母（Δ、Γ、Θ、ν、ρ）、二叉树、隐含波动率 Newton-Raphson 求解器、波动率曲面生成
  - 5 个 API 端点

- **实盘交易桥接** — 5 步起飞前验证（券商、风控配置、业绩、限额、余额），模拟→实盘晋级含风控
  - 2 个 API 端点

- **新手引导向导** — 6 步引导设置（欢迎 → LLM → 数据源 → 自选股 → 策略 → 完成），自动检测已有配置，可关闭
  - 纯前端组件

- **移动端响应式布局** — 自适应侧边栏（移动端折叠 + 遮罩层）、底部导航栏、触控友好 16px 输入框、safe-area-bottom 内边距

- **跨 Worker SSE 总线** — PostgreSQL LISTEN/NOTIFY 发布/订阅层，含进程内回退（`services/sse_bus.py`）

- **GP 性能分析器** — 每代评估计时（p50/p95/p99），数据加载 + 种群初始化追踪（`services/gp_profiler.py`）

- **因子宽表 ETL** — 每日批量任务，计算所有 Alpha Zoo 因子到 `vt_factor_daily_wide` 用于快速筛选查询（`services/factor_wide_etl.py`）

- **LLM 提示词缓存** — SHA-256 去重含 TTL，缓存命中/未命中统计（`services/llm_cache.py`）

- **数据源状态优化** — 缓存 5 分钟 TTL，并行检查（16 workers），每个 loader 1s 超时（原 2s），最坏情况从 46s → ≤10s

### 变更

- **LLM 成本控制** — 速率限制（10 次/分钟），每日 token 预算（500k），通过 `get_llm_usage_stats()` 使用追踪
- **筛选器安全** — 所有条件对照字段/算子白名单验证；字段名消毒
- **GP 适应度** — Walk-forward 交叉验证替代简单训练/测试分割；OOS 稳定性惩罚
- **因子候选** — 新增 `adjusted_p_value` 和 `is_statistically_significant` 字段
- **API 服务器** — 挂载 6 个新路由模块（factor_mining、screener、compare、attribution、scheduler、news）

### 法律

- **免责声明** — README.md 和 README_zh.md 均添加「仅供研究和教育目的，不构成投资建议」

---

## 2026.5.30 — 交易仪表盘

### 新增

- **交易仪表盘**（`/trading`）— 全新的交易统一界面，左侧搜索+自选股 + 右侧 K 线/分时图 + 底部多功能面板
  - 股票搜索框：自选股顶部嵌入 `StockInput` 组件，支持代码/名称/拼音搜索，选中即加入自选股，10s 自动刷新实时价格
  - 分时图（`MinuteLineChart`）：基于 MooTDX 分时数据的 ECharts 组件，价格折线+渐变填充+成交量柱+昨收虚线+十字光标 tooltip，支持午休遮罩区域
  - K 线/分时一键切换：图表区模式切换，分时模式下显示日期选择器
  - 12 个 API 端点：`GET /stock/minute-line`（分时图数据）+ 11 个 trading 端点（OMS 下单/券商状态/通知配置/参数优化 SSE/WS 行情/指数配置/研报资讯）
- **多用户数据隔离** — 3 层安全加固
  - 订单 PostgreSQL 持久化：`vt_trading_orders` 表，参数化 SQL，`WHERE user_id=%s` 全量过滤，服务重启不丢失
  - 券商上下文隔离：`OpenSecTradeContext` 按 `user_id` 缓存，不同用户可连接不同 FutuOpenD 实例
  - WS 订阅隔离：每个用户独立 `set[str]` 订阅列表，互不干扰
  - 通知/指数/优化任务均按用户 JSON 文件或 job ownership 校验隔离
- **数据库迁移** — `migrations/004_trading_orders.sql`，`run_trading_migration()` 启动时自动建表

### 变更

- **i18n 扩展** — 新增约 27 个 trading 相关翻译键（中英双语），覆盖搜索/图表/下单/券商/通知/优化全界面
- **导航扩展** — 侧边栏新增「交易」导航入口，路由 `/trading` 懒加载
- **API 类型扩展** — `types/api.ts` 新增 12 个 TS 接口
- **API 客户端扩展** — `lib/api.ts` 新增 15 个 API 方法

## 2026.5.30 — A 股数据源扩展 + 券商接入

### 新增

- **A 股数据源扩展（4 个新加载器）**
  - `mootdx` — TCP 直连通达信，免费 K 线（日/周/月/1m~60m）+ 五档盘口 + 逐笔成交，不封 IP
  - `eastmoney` — 东财 push2 HTTP K 线，免费日线 + 分钟级，国内最稳定免费 HTTP K 线源
  - `baidu` — 百度股市通 K 线（自带 MA5/MA10/MA20）+ 概念/行业/地域三维板块分类
  - `ths_eps` — 同花顺一致预期 EPS（直连 basic.10jqka.com.cn），用于 PEG/PE 消化计算
- **A 股回退链扩展** — 从 4 源扩展为 8 源（`mootdx→tushare→eastmoney→tencent→futu→baidu→twelvedata→akshare`）
- **PG OHLCV 缓存层** — `cache.py` + `migrations/003_ohlcv_cache.sql`，按 `(code, interval, bar_date)` 缓存 K 线，自动回写
- **并发数据获取** — `fetch_concurrent()` ThreadPoolExecutor，20 只股票 3-5x 加速

- **订单管理系统 (OMS)** — `src/trading/oms.py`，6 状态订单生命周期（PENDING→SUBMITTED→PARTIAL→FILLED/CANCELLED/REJECTED），PG 持久化
- **富途券商接入** — `src/trading/brokers/futu_broker.py`，下单/撤单/查单/查持仓/查账户
- **告警通知系统** — `src/notify/`，Webhook（企业微信/钉钉/Discord/Slack）+ SMTP 邮件，止损/止盈/日亏损/回撤/异常 5 类告警
- **WebSocket 实时行情** — `src/trading/ws_feed.py`，OKX + 东财 push2 WebSocket

- **信号层/资金面数据源（4 个模块）**
  - `eastmoney_datacenter.py` — 东财统一 API，龙虎榜/解禁/融资融券/大宗交易/股东户数/分红/行业排名
  - `fund_flow.py` — 分钟级 + 120 日日级资金流（主力/大单/中单/小单/超大单）
  - `ths_hot.py` — 同花顺当日强势股 + 题材归因
  - `northbound.py` — 沪深股通分钟流向 + 本地 CSV 自缓存历史
- **回测引擎基于市场选择** — `_create_market_engine` 从硬编码源名改为基于 `markets` 属性动态选择
- **参数优化引擎** — `src/optimize/`，Grid / Random / Bayesian 三种搜索模式，SSE 流式进度
- **Walk-Forward 分析** — N 窗口滚动优化 + IS/OOS 一致性 + 参数稳定性
- **投资组合风险度量** — VaR（历史+参数法）/CVaR/Kelly 公式/回撤熔断/行业集中度
- **Black-Litterman 模型** — 贝叶斯融合均衡收益 + 主观观点 → 均值-方差优化
- **压力测试** — 6 种预设场景（2008/2015/2020/2024/flash/stagflation）+ 自定义场景
- **PDF 报告导出** — HTML→PDF（weasyprint），含指标卡片/交易明细/风险度量
- **数据源状态面板** — 新建 `/data-sources` 页面 + 路由，实时显示所有 loader 可用状态 + 健康度

### 修复

- **会话页切回 loading 卡死** — `Agent.tsx` 的 `loadSessionMessages()` try/catch 改为 try/finally
- **Docker build 失败** — Dockerfile 仍引用已删除的 `README_EN.md`，改为 `README_zh.md`

### 安全

- **强制改密** — `ADMIN_PASSWORD` 未配置时自动生成 16 位随机密码
- **API 异常屏蔽** — 25 处 `HTTPException(detail=str(e))` 替换为通用消息
- **补漏认证** — `/swarm/presets` 端点加认证依赖

---

## 2026.5.27 — 模拟盘增强 + 核心修复

### 修复

- **模拟盘 `use_intraday_stop` 启动报错** — `RiskConfig` 缺少 `use_intraday_stop` 字段
- **停牌期信号污染** — 位置矩阵移除 ffill，停牌/非交易日仓位归零
- **幸存者偏差未检测** — 数据拉取后检测无数据的 codes，追加警告到结果
- **auto source 年化系数漂移** — 补齐 tencent/futu/finnhub/twelvedata/auto 交易日历
- **非标 interval 年化错误** — 周线 252→52，4W→13 等

### 新增

- **模拟盘 K 线实时显示** — SSE 实时追加新蜡烛，不再依赖「快速回测」
- **基准对比指标** — `calc_metrics()` 新增 `beta` 计算
- **前端滑点配置** — ChartPanel 新增滑点输入框
- **核心引擎测试覆盖** — 33 个新测试（RiskPipeline/LiveDriver/TradingEngine）
- **SSE 重连抖动** — ±25% 随机抖动量，防惊群效应

---

## 2026.5.26 — 可视化策略构建器 + 前瞻性偏差修复

### 新增

- **自定义模式（可视化策略/指标构建器）** — 下拉框/滑块/开关可视化配置入场/出场规则
- **AI 对话面板** — 自然语言描述，AI 流式生成代码直接写入编辑器
- **圆角卡片式页面布局** — 新增 `.section-card` CSS 类

### 修复

- **回测引擎前瞻性偏差（4 项改进）** — Fast 模式逐 bar 扩展窗口、Simulation 模式数据截断、止损/止盈支持 bar 内高低价、开盘价涨跌停判断
- **MCP 服务器设计缺陷（5 项修复）** — 轮询阻塞、文件操作失效、线程泄漏、错误吞没、凭证泄露
- **Alpha 因子库调用报错** — `df["close"]` → `df[["close"]]`

### 变更

- **Lab 模块重组** — sandbox→security、repository→lab/storage
- **Docker Compose 合并** — pg 配置合并入主文件
- **API 版本化** — 所有路由挂载 `/v1` 前缀
- **前端类型拆分** — API 合约类型提取到 `types/api.ts`
- **前端 UX 全面优化** — 回测指标卡片化、模拟盘代码/预览分离、快速部署、风控保存、自选股实时价格等 15+ 项改进

---

## 2026.5.25 — TradingEngine 统一引擎

### 新增

- **TradingEngine — 统一回测和实盘执行引擎** — 回测和模拟盘共享同一套 `on_bar()` 管道
  - `TradingEngine` — 统一管道：market hooks → 信号生成 → 优化器 → 风控检查 → 状态机约束 → 撮合执行 → 权益快照
  - `SignalAdapter` — 自动检测 batch/tick 模式
  - `BacktestDriver` — 快速模式 + 模拟模式
  - `LiveDriver` — 异步实盘循环
  - `OptimizerAdapter` — 滚动窗口在线组合优化
  - `RiskPipeline` — 止损/止盈/追迹止损/日内亏损限制
- **前端测试基础设施** — vitest + testing-library + jsdom

### 变更

- **api_server.py 拆分** — 2650 行拆分为 6 个路由模块，缩减 88%
- **SSE 管理统一** — 提取 `lib/sseClient.ts` 共享工具

### 修复

- **user_id 硬编码** — 26 处防御性回退替换
- **auth 端点速率限制** — 5 次/分钟防暴力破解

---

## 2026.5.24 (晚间) — 模拟盘 + 技能管理

### 新增

- **Skill 管理** — 87 个技能包，每用户独立启用/禁用
- **MCP 服务设置** — 管理员可见，自动生成配置示例
- **模拟盘策略库** — 从策略实验室/AI 聊天导入策略
- **模拟盘增强** — Monaco 编辑器、K 线预览、部署前验证、自动启动、快速回测、月度热力图、运行日志等 15+ 项功能
- **红涨绿跌全项目覆盖** — `html[lang="zh"]` 自动切换

### 修复

- **TUSHARE_TOKEN 配置被反转清除** — 条件取反 bug
- **Tencent loader 大小写** — normalize 返回大写，API 只接受小写
- **策略沙箱 `__import__` 缺失** — 手工构建 `__builtins__` 漏掉关键函数
- 其他 7 项修复

---

## 2026.5.24 — 多数据源 + 多用户安全

### 新增

- **股票自动联想** — A 股/港股/指数智能搜索
- **模拟盘交易** — 完整 Paper Trading 引擎
- **多数据源扩展** — 6 个新加载器（Tencent、Global Indices、Commodities、CoinGecko、Twelve Data、Finnhub）
- **国际化补齐** — Login、UserManagement 等全部接入 i18n

### 变更

- **全局 UI 重构** — 字号体系、间距系统、按钮层级、卡片阴影、Tab 选中态
- **侧边栏重设计** — 品牌 Logo 橙色圆角底色、导航项 rounded-lg 激活态

### 修复

- **密码哈希升级** — SHA256→PBKDF2-HMAC-SHA256
- **JWT_SECRET 持久化** — 解决多 worker 密钥不一致
- 其他 8 项安全/质量修复

---

## 2026.5.24 (早间)

- **PostgreSQL 自动部署** — `setup.sh` 可选自动部署 PG 16
- **相关性矩阵增强** — 结果 localStorage 持久化
- **JWT 鉴权合并** — 三个鉴权函数合并为 `require_auth`
- 其他 10+ 项修复和改进

---

## 2026.5.23 — 初始版本

AStockPursue 基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License) 二次开发。
