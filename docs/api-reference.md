# AStockPursue API Reference

Base URL: `/api/v1`

## Public Endpoints (No Auth)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/register` | Register a new user account |
| `POST` | `/api/v1/auth/login` | Login and receive a JWT token |
| `GET` | `/api/v1/system/status` | Get system status overview |
| `GET` | `/api/v1/system/ping` | Simple ping health check |
| `GET` | `/health` | Full system health check |
| `GET` | `/ws` | WebSocket connection (real-time data) |

---

## Protected Endpoints (Auth Required)

All endpoints below require a valid JWT token in the `Authorization` header:
```
Authorization: Bearer <token>
```

### Backtest

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/backtest` | Run a new backtest |
| `GET` | `/api/v1/backtest` | List all backtest results |
| `GET` | `/api/v1/backtest/:id` | Get a specific backtest result |

### Trading

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/trading/start` | Start the trading engine |
| `POST` | `/api/v1/trading/stop` | Stop the trading engine |
| `GET` | `/api/v1/trading/status` | Get current trading status |
| `GET` | `/api/v1/trading/orders` | List all orders |
| `POST` | `/api/v1/trading/orders` | Place a new order |
| `DELETE` | `/api/v1/trading/orders/:id` | Cancel a pending order |

### Market Data

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/market/bars` | Get OHLCV bar data for symbols |
| `GET` | `/api/v1/market/symbols` | List available trading symbols |

### Broker Integration

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/broker/account` | Get broker account information |
| `GET` | `/api/v1/broker/positions` | Get broker positions |
| `GET` | `/api/v1/broker/list` | List available brokers |
| `POST` | `/api/v1/broker/connect` | Connect to a broker |
| `POST` | `/api/v1/broker/disconnect` | Disconnect from a broker |
| `POST` | `/api/v1/broker/credentials` | Save broker credentials |

### Portfolio

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/portfolio` | Get portfolio status (positions, equity, PnL) |

### Paper Trading

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/paper-trading` | Create a new paper trading run |
| `GET` | `/api/v1/paper-trading` | List all paper trading runs |
| `GET` | `/api/v1/paper-trading/:id` | Get a specific paper trading run |
| `POST` | `/api/v1/paper-trading/:id/start` | Start a paper trading run |
| `POST` | `/api/v1/paper-trading/:id/stop` | Stop a paper trading run |
| `DELETE` | `/api/v1/paper-trading/:id` | Delete a paper trading run |

### Settings

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/settings` | Get current settings |
| `PUT` | `/api/v1/settings` | Update settings |
| `DELETE` | `/api/v1/settings` | Reset settings to defaults |

### Analysis

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/analysis/correlation` | Run correlation analysis |
| `GET` | `/api/v1/analysis/drawdown` | Get drawdown analysis |
| `POST` | `/api/v1/analysis/attribution` | Run attribution analysis |
| `POST` | `/api/v1/analysis/stress-test` | Run stress test |

### Scheduler

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/scheduler` | Create a scheduled job |
| `GET` | `/api/v1/scheduler` | List all scheduled jobs |
| `GET` | `/api/v1/scheduler/:id` | Get a specific job |
| `POST` | `/api/v1/scheduler/:id/start` | Start a scheduled job |
| `POST` | `/api/v1/scheduler/:id/pause` | Pause a scheduled job |
| `DELETE` | `/api/v1/scheduler/:id` | Delete a scheduled job |

### Screener

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/screener` | Run stock screening with filters |
| `GET` | `/api/v1/screener/movers` | Get top market movers |
| `GET` | `/api/v1/screener/overview` | Get market overview statistics |

### Factors

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/factors` | List available factors |
| `POST` | `/api/v1/factors/compute` | Compute a factor |
| `POST` | `/api/v1/factors/gp-mining` | Start genetic programming factor mining |

> Returns 503 if the Python gRPC service is unavailable.

### Workflow

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/workflow` | List all workflows |
| `POST` | `/api/v1/workflow` | Create or update a workflow |
| `POST` | `/api/v1/workflow/execute` | Execute a workflow |
| `GET` | `/api/v1/workflow/node/:id` | Get a node execution result |

### Signals

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/signals` | List all trading signals |
| `POST` | `/api/v1/signals/generate` | Generate new signals |
| `PUT` | `/api/v1/signals/:id/ack` | Acknowledge a signal |
| `PUT` | `/api/v1/signals/:id/dismiss` | Dismiss a signal |

### Research

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/research/:type` | Run research analysis by type |
| `GET` | `/api/v1/research/:type/:symbol/history` | Get historical research data for a symbol |

### ML Models

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/ml/models` | List all ML models |
| `POST` | `/api/v1/ml/models` | Create a new ML model |
| `GET` | `/api/v1/ml/models/:id` | Get a specific ML model |
| `POST` | `/api/v1/ml/models/:id/archive` | Archive a model |
| `POST` | `/api/v1/ml/models/:id/train` | Train a model |

### Notifications

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/notifications` | List all notifications |
| `POST` | `/api/v1/notifications` | Send a notification |
| `POST` | `/api/v1/notifications/:id/read` | Mark a notification as read |
| `POST` | `/api/v1/notifications/read-all` | Mark all notifications as read |

---

## Authentication

- Register: `POST /api/v1/auth/register` with `{"username": "...", "password": "..."}` (min 6 chars)
- Login: `POST /api/v1/auth/login` with `{"username": "...", "password": "..."}`
- Both return `{"token": "...", "username": "..."}`
- JWT tokens expire after 24 hours

## Rate Limiting

- Registration: 5 attempts per minute per IP address
- Login: 5 attempts per minute per username
- Exceeded limits return `429 Too Many Requests`
