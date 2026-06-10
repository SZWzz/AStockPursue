# Testing Guide

## Test Framework

- **Backend**: pytest (Python 3.11+)
- **Frontend**: vitest + Testing Library

## Test Markers

Backend tests use three pytest markers defined in `pyproject.toml`:

| Marker | Description | When to Run |
|--------|-------------|-------------|
| `@pytest.mark.unit` | Fast, no network, no external dependencies | Always |
| `@pytest.mark.integration` | May spawn local servers, no external APIs | Pre-merge |
| `@pytest.mark.slow` | Spawns subprocesses, no xdist parallelism | Nightly CI |

## Running Tests

```bash
# All fast tests (recommended for local dev)
cd backend && pytest -m "not slow" -x -q

# Unit tests only
cd backend && pytest -m unit -x -q

# Integration tests
cd backend && pytest -m integration -x -q

# Slow tests (MCP integration)
cd backend && pytest -m slow -x -q

# Frontend type-check
cd frontend && npx tsc --noEmit
```

## Test Isolation

The test suite enforces strict isolation:

- **Network**: `pytest-socket` disables all sockets in factor tests (`tests/factors/conftest.py`). Unit tests use `monkeypatch` to mock external libraries.
- **Filesystem**: `tmp_path` fixture is used consistently for temporary files.
- **Environment variables**: `monkeypatch.setenv` / `patch.dict(os.environ)` isolates env-dependent code.
- **External APIs**: All data source loaders (AKShare, Tushare, Futu, CCXT, OKX) are mocked with scripted fakes at the library boundary.

## Writing New Tests

1. Use `@pytest.mark.unit` for tests that don't need external dependencies
2. Use `@pytest.mark.integration` for tests that spawn local servers
3. Use `@pytest.mark.slow` for tests that are too slow for parallel execution
4. Always mock external APIs — never call real market data APIs in tests
5. Use `tmp_path` for any file I/O
6. Use `monkeypatch` for environment variables

## CI Pipeline

The GitHub Actions workflow (`.github/workflows/test.yml`) runs:

1. **syntax** — `py_compile` on key entry points (gate job)
2. **test-fast** — `pytest -m "not slow"` with xdist parallelism
3. **test-slow** — `pytest -m slow` (MCP integration tests)
4. **frontend** — `npm ci && npm run build`
