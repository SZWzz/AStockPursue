# Architecture Overview

AStockPursue is an n8n-style visual workflow platform for quantitative research, with 9 market engines, 450+ factors, 89 AI skills, and 58 workflow node types.

## System Layers

```mermaid
graph TB
    subgraph Frontend["Frontend (React 19 + TypeScript)"]
        WC[Workflow Canvas<br/>@xyflow/react]
        Pages[Pages: Dashboard, Screener,<br/>Trading, Factor Mining, ...]
        Stores[Zustand Stores x9]
    end

    subgraph Backend["Backend (Python 3.11 + FastAPI)"]
        API[REST API Layer<br/>/api/v1/*]
        WE[Workflow Engine<br/>58 node types, Kahn + asyncio]
        TE[Trading Engine<br/>9 market engines]
        FM[Factor Mining<br/>GP Evolution + KB]
        AG[AI Agent<br/>89 skills, 11 LLM providers]
    end

    subgraph Data["Data Layer"]
        PG[(PostgreSQL 14+<br/>Sessions, Orders, KB)]
        PQ[(Parquet Local Store)]
        LD[Loader Registry<br/>23 data sources]
    end

    subgraph External["External"]
        LLM[LLM Providers<br/>OpenAI / Anthropic / ...]
        API2[Market Data APIs<br/>Tushare / AKShare / OKX / ...]
        BROKER[Broker APIs<br/>FutuOpenD]
    end

    Frontend --> Backend
    Backend --> Data
    Backend --> External
    API --> WE
    API --> TE
    API --> FM
    API --> AG
```

## Backend Package Map

```
backend/
├── api_server.py            # FastAPI entry point (port 8899)
├── mcp_server.py            # MCP server (stdio / SSE :8900)
├── cli.py                   # Interactive CLI
├── backtest/                # Backtesting core
│   ├── data_store.py        # 3-tier data access (PG → Parquet → Loader)
│   ├── engines/             # 9 market engines (A-share, US, HK, crypto, forex, futures, options, composite)
│   ├── loaders/             # 23 self-registering data source loaders
│   ├── metrics.py           # Sharpe, Sortino, Calmar, max drawdown, etc.
│   └── runner.py            # Backtest orchestrator
├── src/
│   ├── api/                 # Route handlers (REST endpoints)
│   ├── agent/               # LLM agent loop
│   ├── auth/                # JWT auth, PBKDF2, user config
│   ├── db/                  # Connection pool (psycopg2), async wrapper
│   ├── factors/             # Factor mining (GP engine, KB, registry, safety validator)
│   ├── lab/                 # Strategy lab (backtest bridge, storage, templates)
│   ├── skills/              # 89 AI skill packs (SKILL.md + examples)
│   ├── trading/             # Trading engine, risk pipeline, signal adapter
│   ├── workflow/            # Workflow engine, 58 node types, templates
│   └── tools/               # MCP tools, background tools, research tools
└── tests/                   # 100+ test files (unit / integration / slow markers)
```

## Data Flow: Workflow Execution

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as REST API
    participant WE as WorkflowEngine
    participant Node as Node Executor
    participant DB as PostgreSQL

    U->>FE: Click "Run Workflow"
    FE->>API: POST /workflows/{id}/runs
    API->>DB: Insert run record
    API->>WE: execute(workflow, input)
    loop Each Node (Kahn order)
        WE->>Node: node.execute(context)
        Node-->>WE: output data
        WE->>DB: Snapshot intermediate state
    end
    WE-->>API: final result
    API-->>FE: SSE stream updates
    FE-->>U: Real-time progress + results
```

## Trading Engine Pipeline

The unified `TradingEngine.on_bar()` processes every bar through the same pipeline for both backtest and live trading:

```mermaid
graph LR
    A[New Bar] --> B[Gap Detection]
    B --> C[Suspension Detection]
    C --> D[Market Hooks]
    D --> E[SignalAdapter]
    E --> F[OptimizerAdapter]
    F --> G[RiskPipeline]
    G --> H[Process Signals]
    H --> I[Record Equity]
```

**Critical ordering**: `_record_bars()` must run AFTER `_generate_signals()` to prevent look-ahead bias.

## Factor Mining Pipeline

```mermaid
graph TB
    R[Random Expression Init] --> E[Evaluate Population]
    E --> F{Fitness Function}
    F --> IC[IC Score]
    F --> Cost[Computational Cost]
    F --> Orth[Orthogonality]
    F --> Astab[Stability]
    G[Evolve Generation] --> E
    F --> G
    E --> KB[Factor Knowledge Base]
    KB --> Life[Lifecycle: discovered → validating → approved → production]
```

## Deployment Topology

```mermaid
graph TB
    subgraph Docker["Docker Compose"]
        B[Backend :8899]
        M[MCP Server :9000]
        FE[Frontend :5899]
        PG[(PostgreSQL :5432)]
    end

    subgraph Local["Local Dev"]
        BE2[python api_server.py]
        FE2[npx vite --port 5899]
    end

    Browser --> FE
    Browser --> FE2
    LLM --> M
    LLM --> B
    B --> PG
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| 3-tier data access (PG → Parquet → Loader) | Cache hot data in PG, warm in Parquet, cold fetch from APIs. 8-source A-share fallback for reliability. |
| SignalAdapter dual-mode (tick + batch) | Tick mode for live trading efficiency; batch mode for backtest accuracy with look-ahead prevention. |
| GP evolution with FDR correction | Benjamini-Yekutieli for correlated tests (not BH). Non-overlapping walk-forward windows ensure OOS IC independence. |
| Self-registering loaders | Each data source declares `is_available()` with real connectivity check, not just `import`. |
| FactorKB SHA256 dedup | Identity is `formula_hash` (canonical), never `formula` (display string varies with commutative ops). |
| Single-threaded backtest | `_active_symbol` shared state is safe by design. Each engine has its own market instance. |
