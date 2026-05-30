---
name: mootdx
category: data-source
description: MooTDX — TCP direct connection to TDX (通达信) for A-share K-line data. Free, no API key, no IP blocking. Supports daily/weekly/monthly/minute OHLCV + level-2 order book + tick-by-tick trades.
---

# MooTDX (通达信 TCP 直连)

## Overview

MooTDX connects directly to TDX (通达信) servers via TCP protocol, providing **free A-share market data without any API key or registration**. Unlike HTTP-based data sources, TCP connections are not subject to IP-based rate limiting.

- **K-line**: daily / weekly / monthly / 1m / 5m / 15m / 30m / 60m
- **分时图 (Minute line)**: per-minute price/volume/amount for a single trading day
- **Level-2**: 五档盘口 (5-level order book) + 逐笔成交 (tick-by-tick)
- **No auth**: no registration, no token, no IP blocking
- **Speed**: TCP direct connection, lower latency than HTTP polling

The project has a built-in MooTDX DataLoader at `backtest/loaders/mootdx_loader.py`. When backtesting, set `source: "mootdx"` or rely on `source: "auto"` (MooTDX is the **#1 fallback** for A-shares).

## Quick Start

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market="std")

# Daily K-line
bars = client.bars(symbol="600519", frequency=9, start=0, offset=100)

# Minute K-line (1m=8, 5m=0, 15m=1, 30m=2, 60m=3)
bars = client.bars(symbol="000001", frequency=8, start=0, offset=50)

# Level-2 order book
orders = client.quotes(symbol=["600519", "000001"])

# Tick-by-tick
transactions = client.transaction(symbol="600519", start=0, offset=10)
```

## 分时图 (Minute Line) — Per-Minute Price Trace

The DataLoader exposes two dedicated methods for 分时图 data (not OHLCV K-line — this is the actual tick-level price trace per minute):

### Single stock, single day

```python
from backtest.loaders.mootdx_loader import DataLoader

loader = DataLoader()

# Fetch 分时图 for 贵州茅台 on a specific date
df = loader.fetch_minute_line("600519.SH", "2026-05-29")
# Returns DataFrame indexed by time, columns: price, volume, amount
# None on non-trading days or errors
```

### Multiple stocks, date range

```python
# Fetch 分时图 for multiple stocks over a week
result = loader.fetch_minute_lines(
    ["600519.SH", "000001.SZ"],
    "2026-05-25", "2026-05-29",
)
# Returns: {code: {date_str: DataFrame | None}}
# e.g. result["600519.SH"]["2026-05-29"] -> DataFrame(time, price, volume, amount)
```

### Direct mootdx API (for custom use)

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market="std")

# Today's minute line (live)
df = client.minute(symbol="600519")

# Historical minute line (specific date)
df = client.minutes(symbol="600519", date="2026-05-29")
```

### Limitations

- **History**: TDX server only keeps ~5–10 trading days of minute-line data
- **Non-trading days**: returns `None` (weekends, holidays, suspended)
- **Format**: This is NOT OHLCV — each row is one minute's price/volume/amount
- **For intraday backtesting**: use `interval="1m"` with the standard `fetch()` method (1-minute OHLCV bars)
- **For 分时图 visualization**: use `fetch_minute_line()` / `fetch_minute_lines()`

## Available Intervals (K-line)

| Interval | frequency | Description |
|----------|-----------|-------------|
| 1m | 8 | 1-minute bars |
| 5m | 0 | 5-minute bars |
| 15m | 1 | 15-minute bars |
| 30m | 2 | 30-minute bars |
| 60m | 3 | 60-minute bars |
| 1D | 9 | Daily bars (default) |
| 1W | 5 | Weekly bars |
| 1M | 6 | Monthly bars |

## Notes

- Code format: `600519.SH` or just `600519` (the DataLoader normalizes automatically)
- No authentication or API key required
- TCP port (7709) must be accessible — no special firewall rules needed in most environments
- Not available on PyPI by default — the project installs it via `pip install --no-deps mootdx` to avoid the httpx version conflict
