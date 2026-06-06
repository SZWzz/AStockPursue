<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-14+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Factors-450+-orange?style=flat-square" alt="Alpha Factors">
  <img src="https://img.shields.io/badge/Data_Sources-23-blue?style=flat-square" alt="Data Sources">
  <img src="https://img.shields.io/badge/AI_Skills-89-purple?style=flat-square" alt="AI Skills">
  <img src="https://img.shields.io/badge/Workflow_Nodes-51-teal?style=flat-square" alt="Workflow Nodes">
  <img src="https://img.shields.io/badge/Version-v2026.6.6-blueviolet?style=flat-square" alt="Version">
</p>

<h1 align="center">🚀 AStockPursue</h1>
<p align="center"><strong>AI-Powered Quantitative Research Workflow Platform</strong></p>
<p align="center">
  <sub>n8n-style visual pipeline editor — drag, connect, and run your entire quant research workflow</sub>
  <br>
  <sub><a href="README_zh.md">📖 中文文档</a> · <a href="CHANGELOG.md">📋 Changelog</a></sub>
</p>

---

Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License).

> ⚠️ **Disclaimer**: This software is for **research and educational purposes only**. It does not constitute investment advice. The authors assume no responsibility for any trading losses. **Past performance does not guarantee future results.**

## ✨ Architecture

AStockPursue is an **n8n-style visual workflow platform** for quantitative research. Instead of jumping between 19 disconnected pages, you compose your entire research pipeline on a single canvas:

```
Projects  ──▶  Workflow Canvas  ──▶  Execute & Analyze
                 │
                 ├── Stock Universe ──▶ OHLCV Loader ──▶ Alpha Zoo ──▶ Strategy ──▶ Backtest ──▶ Attribution
                 │
                 └── Chat Input ──▶ AI Agent ──▶ Strategy ──▶ Backtest ──▶ IF (Sharpe > 1?) ──▶ Paper Trading
```

**Every tool** (Strategy Lab, Factor Mining, Screener, etc.) is available as a **typed node** on the canvas, with full-screen editor access for deep dives.

## ✨ Key Features

### 🎨 Visual Workflow Engine
- **12 typed node types** — data loading, alpha computation, strategy building, backtesting, attribution, screening, paper trading, and AI agents — each with typed input/output ports
- **Drag-and-drop canvas** — compose pipelines visually, connections validate type compatibility in real time
- **Concurrent execution** — Kahn's algorithm + asyncio schedules independent nodes in parallel with per-resource semaphores
- **Runtime snapshots** — every run captures the full DAG state; results are always reproducible
- **Node-level execution** — run individual nodes to inspect intermediate outputs before continuing
- **Error recovery** — retry failed nodes, skip non-critical errors, resume from breakpoints
- **Version history** — restore workflows to any previous run state

### 🤖 AI Agent (89 Skills)
- **Natural language → strategy code** — "Build a momentum strategy for CSI 300" generates and backtests a complete SignalEngine
- **AgentNode on canvas** — AI is a workflow node with typed ports: receives prompts + context, outputs code + analysis + factor suggestions
- **ReAct loop** — full tool access across 89 skill packs covering A-shares, crypto, options, macro, risk, factor analysis
- **11 LLM providers** — OpenAI · Anthropic · DeepSeek · Gemini · Moonshot · Zhipu · Grok · Ollama · MiniMax · Qwen · OpenRouter

### 📊 Trading Engine
- **Unified bar-by-bar pipeline** — same engine for backtest and live trading
- **9 market engines** — China A-share (T+1, price limits), US/HK equity, crypto perpetuals, forex, futures (China + global), options
- **Risk pipeline** — stop-loss, trailing-stop, take-profit, max daily loss, position size limits
- **Live trading** — Futu broker integration, real-time WebSocket feeds, OMS

### 🧬 Alpha Factory
- **450+ pre-built factors** — alpha101 (101), gtja191 (191), qlib158 (158), academic, mined
- **GP evolution engine** — genetic programming with composite fitness (IC × complexity × orthogonality), FDR correction, walk-forward validation
- **LLM factor mining** — extract alpha formulas from research papers, debate candidates, hybrid GP+LLM pipeline

### 🔍 Research Tools
- **Smart Screener** — multi-condition stock filtering (AND / rank / score modes) with Alpha Zoo factor integration
- **Performance Attribution** — Brinson, factor, and sector decomposition
- **Strategy Comparison** — statistical tests (paired t, bootstrap, White's reality check), equity overlay
- **News Sentiment** — multi-source aggregation (EastMoney, Wallstreetcn, Sina, Xueqiu), Chinese NLP scoring

### 🏗 Platform
- **Multi-user isolation** — JWT auth, per-user data, broker context, config
- **Scheduled tasks** — cron-based auto-backtest, data health checks, watchlist alerts, workflow scheduling
- **Strategy marketplace** — publish, browse, install, and rate community strategies
- **Version control** — full diff history for strategies, one-click rollback

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript, @xyflow/react (canvas), Zustand (state), ECharts, Monaco Editor, Tailwind CSS |
| **Backend** | Python 3.11+, FastAPI, asyncio, PostgreSQL, psycopg2 |
| **AI/ML** | PyTorch, scikit-learn, SnowNLP, pgvector, LangChain |
| **Data** | pandas, NumPy, Parquet, DuckDB, PostgreSQL cache |
| **Infra** | Docker Compose, Nginx, SSE streaming, JWT auth |

## 🚀 Quick Start

```bash
# Full deploy
docker compose up -d --build              # backend (8899) + MCP (8900)
docker compose --profile pg up -d --build # also auto-deploy PostgreSQL
docker compose --profile frontend up -d   # frontend dev server (5899)

# Backend dev
cd backend && pip install -r requirements.txt
cp .env.example .env
python api_server.py --port 8899          # FastAPI server
python mcp_server.py                      # MCP (stdio)

# Frontend dev
cd frontend && npm install && npx vite --port 5899

# Tests
cd backend && python -m pytest tests/ -x -q
cd frontend && npx tsc --noEmit && npx vitest run
```

## 📁 Project Structure

```
astockpursue/
├── backend/                         # Python backend
│   ├── api_server.py              # FastAPI entry point
│   ├── src/
│   │   ├── workflow/              # ★ Workflow engine (n8n-style)
│   │   │   ├── schema.py          #   typed ports, DAG models
│   │   │   ├── node_base.py       #   BaseNode abstract class
│   │   │   ├── node_registry.py   #   node type registry
│   │   │   ├── workflow_engine.py #   Kahn + asyncio executor
│   │   │   ├── workflow_store.py  #   PostgreSQL persistence
│   │   │   └── nodes/             #   12 node implementations
│   │   │       ├── data_nodes.py  #     StockUniverse, OHLCVLoader
│   │   │       ├── alpha_nodes.py #     AlphaZoo
│   │   │       ├── strategy_nodes.py #  Strategy, Backtest
│   │   │       ├── analysis_nodes.py #  Attribution
│   │   │       ├── thin_nodes.py  #     Screener, PaperTrading
│   │   │       └── control_nodes.py #   ChatInput, Agent, IF
│   │   ├── trading/               # Trading engine + backtest driver
│   │   ├── factors/               # Alpha Zoo + GP mining engine
│   │   ├── services/              # Attribution, screener, sentiment, etc.
│   │   ├── backend/                 # ReAct agent loop, tools, memory
│   │   ├── skills/                # 89 domain skill packs
│   │   └── api/                   # FastAPI route modules (24 routes)
│   ├── backtest/                  # Data store, loaders, engines
│   └── migrations/                # PostgreSQL migrations
├── frontend/                      # React TypeScript frontend
│   └── src/
│       ├── workflow/              # ★ Workflow canvas + store
│       │   ├── canvas/            #   @xyflow/react DAG editor
│       │   ├── store/             #   Zustand state management
│       │   └── types/             #   TypeScript type definitions
│       ├── pages/                 # Page components
│       ├── components/            # Shared UI components
│       ├── stores/                # Zustand stores
│       └── lib/                   # API client, i18n, utilities
└── docs/                          # Documentation
```

## 📄 License

MIT License. Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License).
