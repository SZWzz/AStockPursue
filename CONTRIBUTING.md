# Contributing to AStockPursue

AStockPursue is an AI-powered quantitative trading research platform, built on
[Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (HKUDS, MIT License).

The strategy templates in `agent/src/lab/templates.json` are adapted from
[QuantDinger](https://github.com/QuantDinger/QuantDinger) (Apache License 2.0).

## How to Contribute

### Bug Reports
Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (Docker logs, browser console)

### Feature Requests
Open an issue describing the feature and its use case.

### Pull Requests
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure TypeScript (`npx tsc --noEmit`) and Python (`python3 -m py_compile`) pass
5. Submit a PR with a clear description

## Project Structure

```
AStockPursue/
├── agent/           # Python backend (FastAPI + LangGraph)
│   ├── backtest/    #   Multi-market backtest engine
│   ├── src/lab/     #   Strategy & Indicator Lab
│   ├── src/auth/    #   JWT authentication
│   ├── src/db/      #   PostgreSQL connection pool
│   └── migrations/  #   Database schema
├── frontend/        # React 19 + TypeScript + Tailwind
└── docker-compose.yml
```

## License

This project uses a dual-license structure:

| Scope | License | Copyright |
|-------|---------|-----------|
| Entire project | MIT | (c) 2026 AStockPursue Contributors |
| Base framework | MIT | (c) 2025 HKUDS Vibe-Trading Contributors |
| `agent/src/lab/templates.json` | Apache 2.0 | (c) QuantDinger Contributors |

See [LICENSE](LICENSE) for full details.
