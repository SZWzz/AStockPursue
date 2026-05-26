<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-14+-4169E1?style=flat&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat" alt="License">
  <img src="https://img.shields.io/badge/Factors-450+-orange?style=flat" alt="Alpha Factors">
</p>

<h1 align="center">AStockPursue</h1>
<p align="center"><strong>AI-Powered Quantitative Trading Research Platform</strong></p>

---

Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License).

## Features

<table>
<tr><td width="50%">

### Trading Engine
- **Unified Trading Engine** — Backtest and paper trading share the same `TradingEngine.on_bar()` pipeline. Write a SignalEngine strategy once, run it in both modes
- **Paper Trading** — 3-column layout (library + editor + chart), real-time trade markers, monthly return heatmap, clone runs, pre-deploy validation
- **Lookahead Bias Protection** — Progressive signal generation + data truncation + intraday stop detection + open-price limit checks

### AI Agent
- **AI Chat** — Natural language strategy generation, backtest, and analysis. SSE streaming, 87 skill packs
- **AI Code Generation** — Foldable chat panel below editor — describe your strategy and get code streamed directly into the editor with auto-save
- **MCP Server** — 22 MCP tools for Claude Desktop / Cursor, admin settings panel

### Strategy & Indicator Dev
- **Strategy Lab** — SignalEngine contract editor, K-line backtest panel, 10 templates, backtest history
- **Indicator Lab** — Python indicator IDE (Monaco), sandbox execution, code quality analysis, Alpha Zoo conversion
- **Custom Mode** — No-code visual builder — configure entry/exit rules and risk parameters via dropdowns and sliders, compile to code in one click

</td><td width="50%">

### Factors & Data
- **Alpha Zoo** — 450+ quantitative factors (Alpha101 / GTJA191 / Qlib158 / Academic), user-defined promotion
- **Multi-Source Data** — CN/HK/US/Crypto/Futures/Forex/Indices/Commodities, 13 loaders with auto fallback
- **Non-OHLCV Data** — Market sentiment (VIX/DXY/Yield Curve), fundamentals (PE/PB/ROE), news aggregation
- **Correlation Matrix** — Cross-market correlation (Pearson/Spearman), AI analysis + save to session

### Platform
- **User System** — JWT login/register, per-user LLM/Data Source/Skill config, PBKDF2 hashing, admin panel
- **PostgreSQL Persistence** — Session history, backtest results, strategy/indicator cloud sync, full-text search, auto migration
- **Dark Mode** — Light/dark themes, 4-level surface system (CSS variables)
- **Red-Up/Green-Down** — Chinese market color convention auto-switched per locale
- **i18n** — 150+ translation keys (Chinese / English), auto-detect browser language
- **Card UI** — Rounded card-based layout (`rounded-2xl` + gap spacing), soft modern aesthetic
- **11 LLM Providers** — OpenAI / OpenRouter / DeepSeek / Moonshot / MiniMax / Zhipu / Qwen / Gemini / Groq / Ollama

</td></tr>
</table>

## Tech Stack

| Layer | Stack |
|-------|-------|
| **Backend** | Python 3.11+ · FastAPI · LangChain · Pandas · NumPy · SciPy · PostgreSQL · DuckDB · Pydantic |
| **Frontend** | React 19 · TypeScript · Tailwind CSS · ECharts · Monaco Editor · Zustand · Vite |
| **Data** | Tushare · AKShare · yfinance · OKX · CCXT · Tencent · Twelve Data · Finnhub · CoinGecko · Futu · Global Indices · Commodities · Tiingo |
| **MCP** | FastMCP · 22 tools exposed |
| **Deploy** | Docker · Docker Compose |

## Quick Start

```bash
git clone https://github.com/SZWzz/AStockPursue.git
cd AStockPursue
bash setup.sh                     # optionally auto-deploy PostgreSQL
docker compose up -d --build      # start services
```

> To include auto-deployed PostgreSQL: `docker compose --profile pg up -d --build`

Visit `http://localhost:8899`, login with `admin` / `admin123`, configure LLM and data sources in Settings.

## Project Structure

```
AStockPursue/
├── agent/                     # Python backend
│   ├── api_server.py          #   FastAPI main entry (v1 API)
│   ├── mcp_server.py          #   MCP Server (22 tools)
│   ├── backtest/              #   Multi-market backtest engine + loader registry
│   ├── papertrade/            #   Paper trading engine + scheduler + risk
│   ├── src/
│   │   ├── agent/             #   SkillsLoader + ContextBuilder
│   │   ├── api/               #   FastAPI routes (12 modules)
│   │   ├── auth/              #   JWT auth + per-user encrypted config
│   │   ├── db/                #   PG pool + AES encryption + auto migrate
│   │   ├── factors/           #   Alpha factor registry + zoo (4 families)
│   │   ├── lab/               #   Strategy/Indicator lab (compiler/repo/sandbox/quality)
│   │   ├── session/           #   Session management (PG + file dual store)
│   │   ├── skills/            #   87 skill packs (SKILL.md)
│   │   ├── swarm/             #   Multi-agent collaboration
│   │   ├── tools/             #   MCP tool implementations
│   │   └── trading/           #   Unified trading engine (on_bar pipeline)
│   └── migrations/            #   DB migrations (incremental)
├── frontend/                  # React frontend
│   └── src/
│       ├── pages/             #   Pages (Agent/PTP/IndicatorLab/StrategyLab/AlphaZoo/Settings...)
│       ├── components/        #   Components (chat/indicator-lab/paper-trading/charts/layout)
│       ├── stores/            #   Zustand state management
│       ├── hooks/             #   Custom hooks (SSE/dark mode/backtest)
│       └── lib/               #   Utils + i18n (150+ keys) + API client
├── setup.sh                   # One-click init
├── docker-compose.yml         # Deploy config (with PG profile)
├── CHANGELOG.md               # Changelog
├── README.md                  # 中文文档
└── README_EN.md
```

## License

MIT License. Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS).

Strategy templates in `agent/src/lab/templates.json` originate from [QuantDinger](https://github.com/QuantDinger/QuantDinger) (Apache License 2.0).
