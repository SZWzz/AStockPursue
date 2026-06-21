<p align="center">
  <a href="https://github.com/astockpursue/AStockPursue">
    <img src="docs/assets/logo.png" alt="AStockPursue Logo" width="160">
  </a>
</p>

<h1 align="center">AStockPursue</h1>

<p align="center">
  <strong>AI-Powered Quantitative Research & Trading Workflow Platform</strong>
</p>

<p align="center">
  Go core for high-performance execution · Python layer for AI research · gRPC bridge keeping the boundary clean
</p>

<p align="center">
  <a href="README_zh.md">中文文档</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="docs/">Docs</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Go-1.22+-00ADD8?style=for-the-badge&logo=go&logoColor=white" alt="Go">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Next.js-15-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Factors-450+-orange?style=flat-square" alt="Alpha Factors">
  <img src="https://img.shields.io/badge/Data_Sources-23-blue?style=flat-square" alt="Data Sources">
  <img src="https://img.shields.io/badge/AI_Skills-89-purple?style=flat-square" alt="AI Skills">
  <img src="https://img.shields.io/badge/Workflow_Nodes-58-teal?style=flat-square" alt="Workflow Nodes">
  <img src="https://img.shields.io/badge/i18n-4_languages-06b6d4?style=flat-square" alt="i18n">
  <img src="https://img.shields.io/badge/Version-v2026.6.21-blueviolet?style=flat-square" alt="Version">
</p>

---

> **Disclaimer**: This software is for **research and educational purposes only**. It does not constitute investment advice. The authors assume no responsibility for any trading losses. **Past performance does not guarantee future results.**

## Why AStockPursue?

AStockPursue brings together a **high-performance Go trading engine** and a **Python AI/research layer** into one cohesive workflow platform. You can screen factors, build strategies in natural language, run backtests, and iterate on alpha ideas—without switching contexts.

| What you get | How it helps |
|---|---|
| ⚡ **Unified bar-by-bar pipeline** | Same engine for backtest and live trading, no logic drift |
| 🧠 **Natural language → strategy** | "Build a momentum strategy for CSI 300" generates a full `SignalEngine` and backtests it |
| 🧬 **450+ alpha factors + GP mining** | alpha101, gtja191, qlib158, plus an evolutionary factor discovery engine |
| 🎛️ **Visual workflow canvas** | 58 typed nodes across 10 categories, Kahn-scheduled concurrent execution |
| 🔌 **Multi-broker gateways** | Futu, Binance, OKX with a self-registration pattern |
| 🌍 **8 market engines** | A-share, US/HK equity, crypto perps, forex, China/global futures, options, composite |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 15) — port 5899                         │
│  REST / SSE / WebSocket                                     │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  Go Core Services — port 8899                                 │
│  ├─ HTTP API (gin) — trading, backtest, auth, market          │
│  ├─ Trading Engine — on_bar() pipeline, 8 engine types        │
│  ├─ Market Data — 8 A-share loaders, 3-tier store, WebSocket  │
│  ├─ Broker Gateways — Futu · Binance · OKX                    │
│  ├─ Portfolio / Risk — sizing, margin, stop-loss, OMS        │
│  └─ gRPC Client ──────────────────┐                           │
└─────────────────────────────────┼─────────────────────────────┘
                                  │ gRPC + Protobuf
┌─────────────────────────────────▼─────────────────────────────┐
│  Python Research Layer — ports 8900 / 8902                    │
│  ├─ MCP Server — 22 tools, 89 skills, swarm presets           │
│  ├─ Factor Mining — GP evolution, 450+ alpha zoo              │
│  ├─ AI Agent — ReAct loop, memory, 11 LLM providers           │
│  ├─ Analysis — attribution, sentiment, correlation          │
│  ├─ Workflow Engine — 25 node types, visual pipeline          │
│  └─ gRPC Server — factor, signal, LLM, analysis, workflow   │
└─────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  Data Layer                                               │
│  PostgreSQL 16 · TimescaleDB · Redis 7                    │
└───────────────────────────────────────────────────────────┘
```

**Design philosophy**: Go handles everything latency-sensitive—execution, market data, and risk. Python owns the research-heavy work—factor mining, LLM agents, and workflow orchestration. gRPC keeps the boundary explicit and testable.

## Key Features

### 🚀 Trading Engine (Go)
- **Single pipeline for backtest & live** — one `OnBar()` loop, zero code duplication
- **8 market engines** — China A-share (T+1, price limits), US/HK equity, crypto perpetuals, forex, China futures, global futures, options, composite
- **Risk pipeline** — stop-loss, trailing-stop, take-profit, daily loss limit, position count, OMS state machine
- **Multi-broker** — Futu (A/HK/US stocks), Binance + OKX (crypto) with a pluggable gateway pattern
- **Paper trading** — state machine (`created → running → paused → stopped → error`), in-memory repository
- **Market data** — multi-source loaders, 3-tier store (`cache → TimescaleDB → loader fallback`), WebSocket feed

### 🧠 AI Agent (89 Skills)
- **Natural language → strategy code** — describe an idea, get a backtested `SignalEngine`
- **ReAct loop** — 89 skill packs covering A-shares, crypto, options, macro, risk, factor analysis
- **11 LLM providers** — OpenAI · Anthropic · DeepSeek · Gemini · Moonshot · Zhipu · Grok · Ollama · MiniMax · Qwen · OpenRouter

### 🧬 Alpha Factory
- **450+ pre-built factors** — alpha101 (101), gtja191 (191), qlib158 (158), academic, mined
- **GP evolution engine** — genetic programming with composite fitness (`IC × complexity × orthogonality`), FDR correction, walk-forward validation
- **LLM factor mining** — extract alpha formulas from research papers, debate candidates, hybrid GP+LLM pipeline

### 🎛️ Visual Workflow Engine
- **58 typed nodes** across 10 categories — drag-and-drop canvas with real-time type validation
- **Concurrent execution** — Kahn's algorithm + asyncio parallel scheduling
- **Runtime snapshots** — every run captures the full DAG state; always reproducible

### 📊 Research Tools
- **Smart Screener** — multi-condition stock filtering with Alpha Zoo integration
- **Performance Attribution** — Brinson, factor, and sector decomposition
- **Strategy Comparison** — paired t-test, bootstrap, White's reality check
- **News Sentiment** — multi-source aggregation with Chinese NLP scoring
- **Market Regime Detection** — rule-based classification with strategy family recommendations

### 🛡️ Platform
- **Multi-user isolation** — JWT auth, per-user data and broker credentials
- **Scheduled tasks** — cron-based auto-backtest, data health checks, watchlist alerts
- **Strategy marketplace** — publish, browse, install, and rate community strategies
- **i18n** — English, 简体中文, 日本語, 한국어

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15, React 19, TypeScript, Zustand, Recharts + D3, CodeMirror 6, Tailwind CSS 4, shadcn/ui |
| **Go Core** | Go 1.22+, gin, pgx, rueidis, gRPC client |
| **Python Research** | Python 3.11+, gRPC server, PyTorch, scikit-learn, SnowNLP, pgvector, LangChain |
| **Data** | PostgreSQL 16 + TimescaleDB, Redis 7, pandas, NumPy, Parquet |
| **Infra** | Docker Compose, JWT, SSE streaming, GitHub Actions CI/CD |

## Quick Start

### Full deploy
```bash
docker compose up -d --build              # Go core (8899) + Python (8900/8902)
docker compose --profile pg up -d --build # also deploy PostgreSQL
docker compose --profile frontend up -d   # frontend dev server (5899)
```

### Go core development
```bash
cd services/go && go run ./cmd/server   # HTTP API + gRPC client
```

### Python research layer development
```bash
cd services/python && pip install -r requirements.txt
python mcp_server.py                      # MCP (stdio/SSE, port 8900)
python -m src.grpc.server                 # gRPC server (port 8902)
```

### Frontend development
```bash
cd frontend && npm run dev
```

### Tests
```bash
cd services/go && go test ./...                      # Go unit tests
cd services/python && python -m pytest tests/ -x -q  # Python tests
cd frontend && npx vitest                            # Frontend tests
```

## Project Structure

```
astockpursue/
├── services/
│   ├── go/                         # Go core services
│   │   ├── cmd/server/             #   entry point (gin HTTP + gRPC client)
│   │   ├── internal/
│   │   │   ├── api/handler/        #   REST handlers (16 endpoints)
│   │   │   ├── engine/             #   trading engine (8 types + pipeline + risk + OMS)
│   │   │   ├── market/             #   loaders, store, feed
│   │   │   ├── broker/             #   Futu, Binance, OKX gateways
│   │   │   ├── portfolio/          #   sizing (EqualWeight / Kelly / RiskParity) + margin
│   │   │   ├── papertrade/         #   paper trading engine
│   │   │   └── db/                 #   PostgreSQL + TimescaleDB + Redis
│   │   └── Dockerfile
│   ├── python/                     # Python research layer
│   │   ├── mcp_server.py           #   MCP server (stdio/SSE)
│   │   ├── src/
│   │   │   ├── grpc/               #   gRPC servicers (6 services)
│   │   │   ├── factors/            #   Alpha Zoo + GP evolution engine
│   │   │   ├── agent/              #   ReAct agent loop
│   │   │   ├── skills/             #   89 skill packs
│   │   │   ├── workflow/           #   visual workflow engine
│   │   │   ├── swarm/              #   multi-agent orchestration
│   │   │   ├── tools/              #   MCP tool implementations
│   │   │   └── services/           #   analysis, live bridge
│   │   ├── backtest/               #   loaders + data store (retained for MCP)
│   │   └── tests/
│   ├── proto/                      # Shared Protobuf definitions
│   │   ├── signal.proto
│   │   ├── factor.proto
│   │   ├── llm.proto
│   │   ├── analysis.proto
│   │   ├── workflow.proto
│   │   └── data.proto
│   └── frontend/                   # Next.js frontend
│       ├── app/                    #   App Router pages (27 pages)
│       ├── components/             #   UI + financial components
│       ├── stores/                 #   Zustand state management
│       └── lib/                    #   API client, i18n, utilities
├── docs/                           # Documentation
├── docker-compose.yml
├── CHANGELOG.md
└── CLAUDE.md
```

## License

MIT License. Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License).
