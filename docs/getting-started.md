# Getting Started

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 14+ (or use Docker)
- Git

## Quick Start with Docker

```bash
git clone https://github.com/SZWzz/AStockPursue.git
cd AStockPursue

# Full stack with PostgreSQL
docker compose --profile pg up -d --build

# Frontend dev server
docker compose --profile frontend up -d

# Access
# Frontend: http://localhost:5899
# Backend API: http://localhost:8899
# MCP Server: http://localhost:8900
```

## Local Development

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env    # Edit with your API keys

# Start FastAPI server
python api_server.py --port 8899

# Start MCP server (stdio mode)
python mcp_server.py

# Start MCP server (SSE mode)
python mcp_server.py --transport sse
```

### Frontend

```bash
cd frontend
npm install
npx vite --port 5899
```

### Running Tests

```bash
# Backend tests
cd backend
python -m pytest tests/ -x -q                  # all tests
python -m pytest tests/ -x -q -m "not slow"    # skip slow integration tests
python -m pytest tests/ -x -q -m unit           # unit tests only

# Frontend type-check
cd frontend
npx tsc --noEmit
```

## First-Time Configuration

1. Copy `.env.example` to `.env` and fill in your API keys
2. For A-share data, set `TUSHARE_TOKEN` (free tier available at tushare.pro)
3. For LLM features, set `OPENAI_API_KEY` or configure another provider
4. PostgreSQL connection is configured via `DATABASE_URL` (defaults to local Docker PG)

## Core Concepts

### Workflows

Workflows are visual DAGs of typed nodes. Build them in the Workflow Canvas page:

1. **Data nodes** — Load OHLCV data, factors, or external data
2. **Strategy nodes** — Apply signals, filters, or transformations
3. **Risk nodes** — VaR, stress tests, turnover analysis
4. **Delivery nodes** — Generate PDF reports, export results

### Factor Mining

The Alpha Factory discovers alpha factors via genetic programming:

1. Start from random expression trees
2. Evaluate fitness (IC, cost, orthogonality, stability)
3. Evolve through crossover and mutation
4. Approved factors enter the Factor Knowledge Base with lifecycle tracking

### Trading

Paper trading mode lets you test strategies against live market data:

1. Configure a signal engine (Python script)
2. Set risk parameters (stop-loss, trailing-stop, take-profit)
3. Run in paper mode — orders are simulated without real execution

## Project Structure

```
AStockPursue/
├── backend/
│   ├── api_server.py          # FastAPI entry point
│   ├── backtest/              # Backtesting core
│   ├── src/
│   │   ├── api/               # REST endpoints
│   │   ├── agent/             # LLM agent
│   │   ├── factors/           # Factor mining
│   │   ├── trading/           # Trading engine
│   │   ├── workflow/          # Workflow engine
│   │   └── skills/            # 89 AI skill packs
│   └── tests/                 # Test suite
├── frontend/
│   └── src/
│       ├── pages/             # Page components
│       ├── workflow/          # Workflow canvas
│       ├── stores/            # Zustand state management
│       └── lib/               # API client, i18n
├── docs/                      # This documentation
└── .github/workflows/         # CI/CD
```
