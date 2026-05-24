# Contributing to AStockPursue

AStockPursue is an AI-powered quantitative trading research platform, built on
[Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License).

## How to Contribute

### Bug Reports
Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Browser console logs (F12) and Docker logs (`docker compose logs`)
- Screenshots if applicable

### Feature Requests
Open an issue describing the feature and its use case. Tag with `enhancement`.

### Pull Requests
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Run tests:
   ```bash
   # Frontend TypeScript check
   cd frontend && npx tsc --noEmit
   
   # Backend test suite
   cd agent && python3 -m pytest tests/ -x -q
   ```
5. Submit a PR with a clear description

## Development Setup

### Prerequisites
- Python 3.11+ with `pip`
- Node.js 20+
- PostgreSQL 14+ (or use `docker-compose.pg.yml`)

### Backend
```bash
cd agent
pip install -r requirements.txt
cp .env.example .env   # Edit with your config
python api_server.py --port 8899
```

### Frontend
```bash
cd frontend
npm install
npx vite --port 5899
```

Visit `http://localhost:5899` for dev mode with hot reload.

### MCP Server (optional)
```bash
cd agent
python mcp_server.py                    # stdio transport
python mcp_server.py --transport sse    # SSE transport (port 8900)
```

## Project Structure

```
AStockPursue/
├── agent/                  # Python backend
│   ├── api_server.py       #   FastAPI main entry (8899)
│   ├── mcp_server.py       #   MCP Server (22 tools)
│   ├── backtest/           #   Multi-market backtest engine + loader registry
│   │   └── loaders/        #   13 data source loaders
│   ├── papertrade/         #   Paper trading engine + scheduler + risk manager
│   ├── src/
│   │   ├── agent/          #   SkillsLoader (87 skills) + ContextBuilder
│   │   ├── api/            #   FastAPI routes (6 sub-routers)
│   │   ├── auth/           #   JWT + PBKDF2 + per-user config
│   │   ├── data/           #   Stock symbols (static JSON)
│   │   ├── db/             #   PG pool + AES encryption + auto migrate
│   │   ├── factors/        #   Alpha factor registry + zoo directories
│   │   ├── lab/            #   Strategy/Indicator lab (repo / sandbox / quality)
│   │   ├── session/        #   Session management (file / PG)
│   │   ├── skills/         #   87 skill packs (SKILL.md each)
│   │   ├── swarm/          #   Multi-agent collaboration
│   │   └── tools/          #   22 MCP tools
│   └── migrations/         #   DB migrations (auto-applied on startup)
├── frontend/               # React 19 frontend
│   └── src/
│       ├── pages/          #   Page components
│       ├── components/     #   Shared components
│       ├── stores/         #   Zustand state (agent / paperTrading / auth)
│       ├── hooks/          #   useSSE / useDarkMode
│       └── lib/            #   i18n (100+ keys) / API client / chart theme
├── setup.sh                # One-click init
├── docker-compose.yml      # Main deploy
├── docker-compose.pg.yml   # Auto-deploy PG
└── docs/                   # Project documentation
```

## Architecture Notes

### Data Flow
1. User writes strategy in Strategy/Indicator Lab → Monaco Editor
2. Code passes `validate_code_safety()` (regex + AST double check)
3. Sandbox executes code with restricted `__builtins__` + import whitelist + 30s timeout
4. Data loaders fetch OHLCV via registry → fallback chain → market-specific loader
5. Backtest engine runs vectorized simulation → metrics + equity curve + trade log
6. Results streamed to frontend via SSE or polled via REST API

### Adding a New Data Source
1. Create loader class with `name`, `markets`, `is_available()`, `fetch()` in `agent/backtest/loaders/`
2. Decorate with `@register` — auto-registered on import
3. Add to `_loader_modules` list in `registry.py`
4. Add to `FALLBACK_CHAINS` for relevant markets
5. Optionally add a SKILL.md in `agent/src/skills/` for AI agent guidance

### Adding a New Skill
1. Create directory `agent/src/skills/your-skill/`
2. Add `SKILL.md` with YAML frontmatter (`name`, `description`, `category`)
3. Optional: `example_signal_engine.py`, `references/`, `scripts/`
4. Skill auto-discovered on next server start
5. Users can also ZIP-import skills via Settings → Skill Management

### Frontend Patterns
- **State**: Zustand stores (avoid prop drilling)
- **Charts**: ECharts via `CandlestickChart` / `EquityChart` components
- **i18n**: `useI18n()` hook → `t.keyName`. Add keys to both `en` and `zh` in `i18n.tsx`
- **Colors**: Use `text-up`/`text-down` for direction-specific colors (auto-swaps for zh locale)
- **API calls**: Use `api.*` methods from `lib/api.ts` (centralized auth + error handling)

## Code Style

- **Python**: Type hints required. Follow PEP 8. Use `from __future__ import annotations`.
- **TypeScript**: Strict mode. Use `interface` for props. Avoid `any`.
- **Commits**: Descriptive messages in English. One logical change per commit.

## License

This project uses a multi-license structure:

| Scope | License | Copyright |
|-------|---------|-----------|
| Entire project | MIT | (c) 2025-2026 AStockPursue Contributors |
| Base framework | MIT | (c) 2025 HKUDS Vibe-Trading Contributors |
| `agent/src/lab/templates.json` | Apache 2.0 | (c) QuantDinger Contributors |
| `agent/src/factors/zoo/qlib158/` | Apache 2.0 | (c) Microsoft Corporation |

See [LICENSE](LICENSE) for full details.
