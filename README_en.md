# AStockPursue — AI Quantitative Trading Research Platform

Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License).

## Features

- **AI Agent Chat** — Natural language strategy generation, backtesting, SSE streaming
- **Strategy Lab** — SignalEngine editor, multi-asset portfolio backtesting, auto-save AI strategies
- **Paper Trading** — Full paper trading engine with SignalEngine strategies, SSE real-time ticks, risk management (stop-loss/take-profit/trailing-stop), equity curve visualization, trade history
- **Indicator Lab** — Python indicator IDE (Monaco), sandboxed execution, code quality analysis
- **Alpha Zoo** — 450+ quantitative factors (Alpha101 / GTJA191 / Qlib158)
- **Multi-Source Data** — A-shares / HK / US / crypto / futures / forex / indices / commodities with 10+ loaders (Tencent, Global Indices, Commodities, CoinGecko, Twelve Data, Finnhub) and auto fallback chains
- **Non-OHLCV Data** — Market sentiment (VIX/DXY/Yield Curve), fundamentals (PE/PB/ROE), news aggregation for multi-dimensional analysis
- **Stock Autocomplete** — Smart search for A-shares / HK / indices by code, name, or pinyin
- **Correlation Matrix** — A-shares / HK / US / crypto cross-asset correlation, AI analysis + save to chat
- **User System** — JWT login / register, per-user LLM & data source config, AES-256-GCM encryption
- **User Management** — Admin panel with LLM / Tushare status overview
- **PostgreSQL** — Session history, backtest results, indicator / strategy cloud sync, full-text search
- **11 LLM Providers** — OpenAI / OpenRouter / DeepSeek / Moonshot / MiniMax / Zhipu / Qwen / Gemini / Groq / Ollama

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI / LangChain / LangGraph / Pandas / PostgreSQL
- **Frontend**: React 19 / TypeScript / Tailwind CSS / ECharts / Monaco Editor
- **Data**: Tushare / AKShare / yfinance / OKX / CCXT / Tencent / Twelve Data / Finnhub / CoinGecko / Global Indices / Commodities
- **Deploy**: Docker / Docker Compose

## Prerequisites

- **PostgreSQL 14+** — users, sessions, backtest results, watchlist
- **Docker & Docker Compose**
- (Optional) Tushare Token — A-share market data

## Quick Start

```bash
git clone https://github.com/SZWzz/AStockPursue.git
cd AStockPursue
bash setup.sh                # Optionally auto-deploy PostgreSQL
docker compose up -d --build
```

If you chose auto-deploy PG: `docker compose -f docker-compose.yml -f docker-compose.pg.yml up -d --build`

Open `http://localhost:8899`, login with admin / admin123, configure LLM in Settings.

## Project Structure

```
AStockPursue/
├── agent/             # Python backend
│   ├── backtest/      #   Multi-market backtest engine
│   ├── src/lab/       #   Strategy & Indicator Lab
│   ├── src/auth/      #   JWT authentication
│   ├── src/db/        #   PostgreSQL pool + AES encryption
│   ├── src/api/       #   FastAPI routes
│   └── migrations/    #   Database migrations
├── frontend/          # React frontend
│   └── src/
│       ├── pages/     #   Page components
│       ├── components/#   Shared components
│       ├── stores/    #   Zustand state
│       └── lib/       #   Utilities + i18n
├── setup.sh           # One-click setup script
└── docker-compose.yml
```

## License

MIT License. Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS).

Templates in `agent/src/lab/templates.json` adapted from [QuantDinger](https://github.com/QuantDinger/QuantDinger) (Apache 2.0).
