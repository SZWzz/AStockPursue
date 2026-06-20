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
  <img src="https://img.shields.io/badge/Version-v2026.6.20-blueviolet?style=flat-square" alt="Version">
</p>

<h1 align="center">🚀 AStockPursue</h1>
<p align="center"><strong>AI-Powered Quantitative Research Workflow Platform</strong></p>
<p align="center">
  <sub>Go + Python hybrid microservices — high-performance trading engine meets AI research layer</sub>
  <br>
  <sub><a href="README_zh.md">中文文档</a> · <a href="CHANGELOG.md">Changelog</a></sub>
</p>

---

Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License).

> **Disclaimer**: This software is for **research and educational purposes only**. It does not constitute investment advice. The authors assume no responsibility for any trading losses. **Past performance does not guarantee future results.**

## Architecture

AStockPursue uses a **Go + Python hybrid microservice architecture** connected via gRPC:

```
Frontend (Next.js, port 5899)
    │  REST JSON
Go Core Services (port 8899)
    ├─ HTTP API (gin) — trading, backtest, auth, market
    ├─ Trading Engine — on_bar() pipeline, 8 engine types
    ├─ Market Data — loaders, 3-tier store, WebSocket feed
    ├─ Broker Gateways — Binance, Futu, OKX
    ├─ Portfolio/Risk — sizing, margin, stop-loss
    └─ gRPC Client ────────┐
    │  gRPC + Protobuf      │
Python Research Layer (port 8900/8902)
    ├─ MCP Server — 22 tools, 89 skills, swarm presets
    ├─ Factor Mining — GP evolution, 452 alpha zoo
    ├─ AI Agent — LLM agent, langgraph loop, memory
    ├─ Analysis — attribution, sentiment, correlation
    ├─ Workflow Engine — 25 node types, visual pipeline
    └─ gRPC Server — factor, signal, LLM, analysis, workflow, data
    │  SQL + Pub/Sub
Data Layer
    PostgreSQL 16 + TimescaleDB + Redis 7
```

**Design philosophy**: Go handles performance-critical trading execution and market data pipelines. Python powers the AI/research layer (factor mining, LLM agents, workflow orchestration). Communication via gRPC keeps the boundary clean.

## Key Features

### Trading Engine (Go)
- **Unified bar-by-bar pipeline** — same engine for backtest and live trading
- **8 market engines** — China A-share (T+1, price limits), US/HK equity, crypto perpetuals, forex, China futures, global futures, options, composite
- **Risk pipeline** — stop-loss, trailing-stop, take-profit, max daily loss, position size limits
- **Multi-broker** — Futu (A/HK/US stocks), Binance + OKX (crypto) with self-registration pattern
- **Paper trading** — state machine (created→running→paused→stopped→error), in-memory repository
- **Market data** — 8 A-share loaders + gRPC bridge, 3-tier store (cache → TimescaleDB → loader fallback), WebSocket feed

### AI Agent (89 Skills)
- **Natural language → strategy code** — "Build a momentum strategy for CSI 300" generates and backtests a complete SignalEngine
- **ReAct loop** — full tool access across 89 skill packs covering A-shares, crypto, options, macro, risk, factor analysis
- **11 LLM providers** — OpenAI · Anthropic · DeepSeek · Gemini · Moonshot · Zhipu · Grok · Ollama · MiniMax · Qwen · OpenRouter

### Alpha Factory
- **450+ pre-built factors** — alpha101 (101), gtja191 (191), qlib158 (158), academic, mined
- **GP evolution engine** — genetic programming with composite fitness (IC × complexity × orthogonality), FDR correction, walk-forward validation
- **LLM factor mining** — extract alpha formulas from research papers, debate candidates, hybrid GP+LLM pipeline

### Visual Workflow Engine
- **58 typed nodes** across 10 categories — drag-and-drop canvas with real-time type validation
- **Concurrent execution** — Kahn's algorithm + asyncio parallel scheduling
- **Runtime snapshots** — every run captures full DAG state; always reproducible

### Research Tools
- **Smart Screener** — multi-condition stock filtering with Alpha Zoo factor integration
- **Performance Attribution** — Brinson, factor, and sector decomposition
- **Strategy Comparison** — statistical tests (paired t, bootstrap, White's reality check)
- **News Sentiment** — multi-source aggregation, Chinese NLP scoring
- **Market Regime Detection** — rule-based classification with strategy family recommendations

### Platform
- **Multi-user isolation** — JWT auth, per-user data and broker credentials
- **Scheduled tasks** — cron-based auto-backtest, data health checks, watchlist alerts
- **Strategy marketplace** — publish, browse, install, and rate community strategies
- **i18n** — English, 简体中文, 日本語, 한국어

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15, React 19, TypeScript, Zustand, Recharts + D3, CodeMirror 6, Tailwind CSS 4, shadcn/ui |
| **Go Core** | Go 1.22+, gin, pgx, rueidis, gRPC client |
| **Python Research** | Python 3.11+, gRPC server, PyTorch, scikit-learn, SnowNLP, pgvector, LangChain |
| **Data** | PostgreSQL 16 + TimescaleDB, Redis 7, pandas, NumPy, Parquet |
| **Infra** | Docker Compose, JWT, SSE streaming, GitHub Actions CI/CD |

## Quick Start

```bash
# Full deploy
docker compose up -d --build              # Go core (8899) + Python (8900/8902)
docker compose --profile pg up -d --build # also auto-deploy PostgreSQL
docker compose --profile frontend up -d   # frontend dev server (5899)

# Go core dev
cd services/go && go run ./cmd/server     # HTTP API + gRPC client

# Python research layer dev
cd services/python && pip install -r requirements.txt
python mcp_server.py                      # MCP (stdio/SSE, port 8900)
python -m src.grpc.server                 # gRPC server (port 8902)

# Frontend dev
cd frontend && npm run dev

# Tests
cd services/go && go test ./...           # Go unit tests
cd services/python && python -m pytest tests/ -x -q # Python tests
cd frontend && npx vitest                 # Frontend tests
```

## Project Structure

```
astockpursue/
├── services/
│   ├── go/                         # Go core services
│   │   ├── cmd/server/             #   entry point (gin HTTP + gRPC client)
│   │   ├── internal/
│   │   │   ├── api/handler/        #   REST handlers (16 endpoints)
│   │   │   ├── engine/             #   trading engine (8 types + pipeline + risk)
│   │   │   ├── market/             #   loaders, store, feed
│   │   │   ├── broker/             #   Binance, OKX, Futu gateways
│   │   │   ├── portfolio/          #   sizing (EqualWeight/Kelly/RiskParity) + margin
│   │   │   ├── papertrade/         #   paper trading engine
│   │   │   └── db/                 #   PostgreSQL + TimescaleDB + Redis
│   │   └── Dockerfile
│   ├── python/                     # Python research layer
│   │   ├── mcp_server.py           #   MCP server (stdio/SSE)
│   │   ├── src/
│   │   │   ├── grpc/               #   gRPC servicers (6 services)
│   │   │   ├── factors/            #   Alpha Zoo + GP mining engine
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
