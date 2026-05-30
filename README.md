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
  <img src="https://img.shields.io/badge/MCP_Tools-31-teal?style=flat-square" alt="MCP Tools">
  <img src="https://img.shields.io/badge/Version-2026.5.30-blueviolet?style=flat-square" alt="Version">
</p>

<h1 align="center">🚀 AStockPursue</h1>
<p align="center"><strong>AI-Powered Quantitative Trading Research Platform</strong></p>
<p align="center">
  <sub>Natural language → Strategy generation → Backtest → Optimization → Paper trading — all in one platform</sub>
  <br>
  <sub><a href="README_zh.md">📖 中文文档</a> · <a href="CHANGELOG.md">📋 Changelog</a></sub>
</p>

---

Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License).

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🤖 AI Agent
- **Natural Language Strategy Generation** — Describe your strategy in plain English/Chinese, AI generates the SignalEngine code, runs backtests, and iterates in real time
- **SSE Streaming** — Watch the agent think, call tools, and generate results step by step
- **89 Skill Packs** — Covering the full quant stack: A-shares, crypto, options, macro, risk management, factor analysis, behavioral finance, market microstructure, and more
- **Multi-Agent Swarm** — 29 preset teams (quant desk, macro forum, sector rotation, etc.) for collaborative research
- **Agent Memory** — Persistent file-based memory across sessions
- **11 LLM Providers** — OpenAI · OpenRouter · DeepSeek · Moonshot · MiniMax · Zhipu · Qwen · Gemini · Groq · Ollama · Anthropic

### 📊 Trading Dashboard *(NEW)*
- **Unified Trading Interface** — Left: stock search + watchlist · Right: K-line / minute-line chart + multi-function tabs
- **Stock Search Box** — Code/name/pinyin search at watchlist top, select to add, 10s auto-refresh prices
- **Intraday Minute-Line Chart** — Per-minute price trace via MooTDX, volume bars, pre-close reference line, lunch-break shading, crosshair tooltip
- **One-Click K-Line / Minute Toggle** — Switch between OHLCV candlestick and intraday price trace
- **OMS Panel** — Place market/limit orders, view active & historical orders, cancel with one click
- **Broker Panel** — FutuOpenD connection status, account info, positions table
- **Notify Panel** — Per-channel enable/disable, add webhook/email/SMS, test-send
- **Optimization Panel** — Grid/Random/Bayesian search, SSE progress bar, result display
- **Index Ticker Bar** — Customizable scrolling market index bar with editing popover

### 🔐 Multi-User Isolation
- **Per-User Orders** — PostgreSQL `vt_trading_orders` with `user_id` foreign key, parameterized SQL
- **Per-User Broker Context** — Independent `OpenSecTradeContext` cache per user, different FutuOpenD instances
- **Per-User WS Subscriptions** — Isolated symbol subscription sets
- **Per-User Config** — Notify/indices/optimize all scoped to authenticated user

</td>
<td width="50%" valign="top">

### 📈 Trading Engine
- **Unified Engine** — Backtest and paper trading share the same `TradingEngine.on_bar()` pipeline. Write a SignalEngine once, run in both modes
- **Paper Trading** — 3-column layout (library + editor + chart), real-time trade markers on K-line, monthly return heatmap, clone runs, pre-deploy validation, SSE live streaming
- **Lookahead Bias Protection** — Progressive signal generation + data truncation + intraday stop detection + open-price limit checks + survivorship-bias warnings
- **6-State OMS** — PENDING → SUBMITTED → PARTIAL → FILLED / CANCELLED / REJECTED lifecycle with callback hooks
- **Futu Broker** — Order placement, cancellation, position & account queries via FutuOpenD
- **Alert Engine** — Webhook (WeChat/DingTalk/Discord/Slack) + SMTP email, 5 alert types (stop-loss/take-profit/daily-loss/drawdown/anomaly)

### 🧪 Strategy & Indicator Dev
- **Strategy Lab** — SignalEngine contract editor, K-line backtest with benchmark comparison (β / IR / excess return), configurable slippage, 10 templates, backtest history
- **Indicator Lab** — Python indicator IDE (Monaco), sandbox execution, code quality analysis, Alpha Zoo conversion
- **Custom Mode** — No-code visual builder — configure entry/exit rules and risk parameters via dropdowns and sliders, compile to code in one click

### 🧬 Factors & Data
- **Alpha Zoo** — 450+ quantitative factors across 4 families (Alpha101 / GTJA191 / Qlib158 / Academic), user-defined promotion, benchmark scoring with IC/IR
- **23 Data Sources** — CN / HK / US / Crypto / Futures / Forex / Indices / Commodities
- **8-Source A-Share Fallback Chain** — `mootdx → tushare → eastmoney → tencent → futu → baidu → twelvedata → akshare`
- **3-Tier Data Access** — PostgreSQL cache → Parquet local store → API, with incremental updates and health-aware auto-routing
- **Non-OHLCV Data** — Dragon Tiger Board / lockup expiry / margin trading / block trades / fund flow (minute + 120d daily) / hot stocks + theme attribution / northbound capital / market sentiment
- **Correlation Matrix** — Cross-market correlation (Pearson/Spearman), AI analysis + save to session

### 🏗 Platform
- **User System** — JWT login/register, per-user LLM/Data Source/Skill config, PBKDF2 hashing, admin panel
- **PostgreSQL Persistence** — Sessions, messages, backtest results, strategies, indicators, orders — all in PG with full-text search and auto incremental migration
- **Dark Mode** — Light/dark themes with CSS variable surface system
- **Red-Up/Green-Down** — Chinese market color convention auto-switched per locale (`html[lang="zh"]`)
- **i18n** — 170+ translation keys (Chinese / English), auto-detect browser language
- **Card UI** — Rounded card-based layout (`rounded-2xl`), soft modern aesthetic
- **MCP Server** — 31 MCP tools exposed for Claude Desktop / Cursor integration

</td>
</tr>
</table>

## 🛠 Tech Stack

| Layer | Stack |
|-------|-------|
| **Backend** | Python 3.11+ · FastAPI · LangChain · Pandas · NumPy · SciPy · PostgreSQL · DuckDB · Pydantic |
| **Frontend** | React 19 · TypeScript · Tailwind CSS · ECharts · Monaco Editor · Zustand · Vite |
| **Data** | MooTDX · Tushare · EastMoney · AKShare · Baidu · Tencent · yfinance · OKX · CCXT · Twelve Data · Finnhub · CoinGecko · Futu · Global Indices · Commodities · THS · Northbound · Tiingo |
| **Trading** | Unified Engine · OMS (6-state) · Futu Broker · Risk Pipeline · WebSocket Feed · Alert Engine (Webhook/Email) |
| **Optimize** | Grid / Random / Bayesian Search · Walk-Forward · Monte Carlo · Bootstrap · Black-Litterman · VaR / CVaR · Stress Test |
| **MCP** | FastMCP · 31 tools exposed |
| **Deploy** | Docker · Docker Compose |

## 🚀 Quick Start

```bash
git clone https://github.com/SZWzz/AStockPursue.git
cd AStockPursue
bash setup.sh                     # optionally auto-deploy PostgreSQL
docker compose up -d --build      # start services
```

> For auto-deployed PostgreSQL: `docker compose --profile pg up -d --build`

Visit `http://localhost:8899`, login with `admin` / `admin123`, configure LLM and data sources in Settings.

## 📁 Project Structure

```
AStockPursue/
├── agent/                          # Python backend
│   ├── api_server.py               #   FastAPI main entry (v1 API, 14 route modules)
│   ├── mcp_server.py               #   MCP Server (31 tools)
│   ├── backtest/                   #   Multi-market backtest engine
│   │   ├── engines/                #     Market-specific engines (CN/US/HK/Crypto/Futures)
│   │   ├── loaders/                #     23 data source loaders
│   │   ├── optimizers/             #     5 portfolio optimizers (MV/RP/MD/EV/BL)
│   │   ├── data_store.py           #     3-tier DataStore (cache → store → API)
│   │   ├── portfolio_risk.py       #     VaR/CVaR/Kelly/concentration
│   │   ├── stress_test.py          #     6 preset + custom stress scenarios
│   │   └── report.py               #     HTML→PDF report generator
│   ├── papertrade/                 #   Paper trading engine + scheduler + risk
│   ├── src/
│   │   ├── agent/                  #   SkillsLoader + ContextBuilder
│   │   ├── api/                    #   14 FastAPI route modules
│   │   ├── auth/                   #   JWT auth + per-user encrypted config
│   │   ├── db/                     #   PG pool + AES encryption + auto migrate
│   │   ├── factors/                #   Alpha factor registry + 4 zoo families
│   │   ├── lab/                    #   Strategy/Indicator lab (compiler/repo/sandbox/quality)
│   │   ├── session/                #   Session management (PG + file dual store)
│   │   ├── skills/                 #   89 AI skill packs (SKILL.md)
│   │   ├── swarm/                  #   Multi-agent collaboration presets
│   │   ├── tools/                  #   MCP tool implementations
│   │   ├── notify/                 #   Alert engine (webhook/email, 5 alert types)
│   │   ├── optimize/               #   Param optimization (grid/random/bayesian + walk-forward)
│   │   ├── trading/                #   Unified engine (OMS + brokers/WS feed/risk pipeline)
│   │   └── shadow_account/         #   Trade journal analyzer + shadow account
│   └── migrations/                 #   DB migrations (incremental SQL)
├── frontend/                       # React frontend
│   └── src/
│       ├── pages/                  #   14 pages (Agent/Trading/PTP/IndicatorLab/StrategyLab/...)
│       ├── components/             #   7 component groups (chat/trading/paper-trading/charts/...)
│       ├── stores/                 #   Zustand state management (5 stores)
│       ├── services/               #   API service layer
│       ├── hooks/                  #   Custom hooks (SSE/dark mode/backtest)
│       └── lib/                    #   Utils + i18n (170+ keys) + API client + chart-theme
├── setup.sh                        # One-click init script
├── docker-compose.yml              # Deploy config (with PG profile)
├── CHANGELOG.md                    # Detailed changelog
├── README.md                       # English documentation
└── README_zh.md                    # 中文文档
```

## 📄 License

MIT License. Built on [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS).

Strategy templates in `agent/src/lab/templates.json` originate from [QuantDinger](https://github.com/QuantDinger/QuantDinger) (Apache License 2.0).
