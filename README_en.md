# AStockPursue — AI Quantitative Trading Research Platform

Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License).

## Features

- **Unified Trading Engine** — Backtest and paper trading share the same `TradingEngine.on_bar()` execution pipeline. Write a SignalEngine strategy once, run it in both modes — no more backtest/live behavior divergence
- **AI Agent Chat** — Natural language strategy generation, backtest, and analysis. SSE streaming output, 87 skill packs covering the full quant domain, survives page navigation
- **Strategy Lab** — SignalEngine contract editor, K-line real-time backtest panel, 10 strategy templates, AI-generated strategies auto-saved, backtest history
- **Paper Trading** — 3-column layout (strategy library + code editor + K-line chart), real-time trade markers overlaid, live position updates, monthly return heatmap, run log + signal stats, clone runs, pre-deploy validation
- **Indicator Lab** — Python indicator IDE (Monaco editor), K-line backtest panel, sandbox execution, code quality analysis, Alpha Zoo one-click conversion, safe sys injection
- **Alpha Zoo** — 450+ quantitative factors (Alpha101 / GTJA191 / Qlib158), user-defined promotion
- **Multi-Source Data** — A-share / HK / US / Crypto / Futures / Forex / Indices / Commodities, 13 loaders with auto fallback, Tencent free A-share quotes
- **Non-OHLCV Data** — Market sentiment (VIX/DXY/Yield Curve), fundamentals (PE/PB/ROE), news aggregation
- **Smart Stock Search** — Tencent quote API dynamic CN/HK lookup, free-text US/Crypto input, code/name/pinyin matching
- **Watchlist Panel** — Real-time prices with red-up/green-down (Chinese convention), click to trigger AI analysis
- **Correlation Matrix** — Cross-market correlation (Pearson/Spearman), AI analysis + save to session
- **User System** — JWT login/register, per-user LLM / Data Source / Skill config, PBKDF2 password hashing
- **Skill Management** — 87 skill packs per-user enable/disable, ZIP import custom skills, per-user isolation
- **MCP Server** — 22 MCP tools exposed to Claude Desktop / Cursor, admin settings panel
- **User Management** — Admin panel for all users, global Skill import visibility
- **PostgreSQL Persistence** — Session history, backtest results, strategy/indicator cloud sync, full-text search, auto incremental migration
- **i18n** — 100+ translation keys, auto-detect browser language (Chinese / English)
- **Dark Mode** — Light/dark themes, 4-level surface system, CSS variable driven
- **Red-Up/Green-Down** — `html[lang="zh"]` auto-switches Chinese market color convention across K-line, equity curves, and P&L display
- **11 LLM Providers** — OpenAI / OpenRouter / DeepSeek / Moonshot / MiniMax / Zhipu / Qwen / Gemini / Groq / Ollama

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.11+ / FastAPI / LangChain / Pandas / PostgreSQL / Pydantic |
| Frontend | React 19 / TypeScript / Tailwind CSS / ECharts / Monaco Editor / Zustand |
| Data | Tushare / AKShare / yfinance / OKX / CCXT / Tencent / Twelve Data / Finnhub / CoinGecko / Futu / Global Indices / Commodities |
| MCP | FastMCP / 22 tools exposed |
| Deploy | Docker / Docker Compose |

## Prerequisites

- **PostgreSQL 14+** — stores users, sessions, backtest results, watchlist, etc.
- **Docker & Docker Compose** — containerized deployment
- (Optional) Tushare Token — for A-share data

## Quick Start

```bash
git clone https://github.com/SZWzz/AStockPursue.git
cd AStockPursue
bash setup.sh                     # optionally auto-deploy PostgreSQL
docker compose up -d --build
```

To include auto-deployed PG: `docker compose -f docker-compose.yml -f docker-compose.pg.yml up -d --build`

Visit `http://localhost:8899`, login with `admin` / `admin123`, configure LLM and data sources in Settings.

## Project Structure

```
AStockPursue/
├── agent/                  # Python backend
│   ├── api_server.py       #   FastAPI main entry
│   ├── mcp_server.py       #   MCP Server (22 tools)
│   ├── backtest/           #   Multi-market backtest engine + loader registry
│   ├── papertrade/         #   Paper trading engine + scheduler + risk (re-exports from src/trading)
│   ├── src/
│   │   ├── agent/          #   SkillsLoader + ContextBuilder
│   │   ├── api/            #   FastAPI routes
│   │   ├── auth/           #   JWT auth + per-user config (Token/Skill)
│   │   ├── data/           #   Stock symbol static data
│   │   ├── db/             #   PG connection pool + AES encryption + auto migrate
│   │   ├── factors/        #   Alpha factor registry + zoo directory
│   │   ├── lab/            #   Strategy/Indicator lab (repo / sandbox / quality)
│   │   ├── session/        #   Session management (file / PG)
│   │   ├── skills/         #   87 skill packs (SKILL.md)
│   │   ├── swarm/          #   Multi-agent collaboration
│   │   ├── tools/          #   22 MCP tools
│   │   └── trading/        #   Unified trading engine (shared on_bar pipeline)
│   └── migrations/         #   DB migrations (incremental)
├── frontend/               # React frontend
│   └── src/
│       ├── pages/          #   Pages (Agent / PaperTrading / IndicatorLab / StrategyLab / AlphaZoo / Settings)
│       ├── components/     #   Shared components (chat / indicator-lab / paper-trading / charts)
│       ├── stores/         #   Zustand state management
│       ├── hooks/          #   Custom hooks (SSE / dark mode)
│       └── lib/            #   Utils + i18n (100+ keys) + API client
├── setup.sh                # One-click init script
├── docker-compose.yml      # Main deploy config
├── docker-compose.pg.yml   # PG container config
├── README.md               # 中文文档
├── README_EN.md            # English docs
└── CHANGELOG.md
```

## License

MIT License. Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS).

Strategy templates in `agent/src/lab/templates.json` originate from [QuantDinger](https://github.com/QuantDinger/QuantDinger) (Apache License 2.0).
