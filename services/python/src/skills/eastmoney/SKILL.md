---
name: eastmoney
category: data-source
description: EastMoney (东方财富) push2 HTTP K-line for A-shares. Free, no API key. The most stable free HTTP K-line source for Chinese stocks. Supports daily + minute-level OHLCV (1m/5m/15m/30m/60m).
---

# EastMoney (东方财富 push2)

## Overview

EastMoney provides **free A-share K-line data** via the push2 HTTP API, widely regarded as the **most stable free HTTP K-line source** for the Chinese market. No registration or API key required.

- **Daily+Minute K-line**: 1D / 1W / 1M / 1m / 5m / 15m / 30m / 60m
- **前复权**: adjusted close (forward-adjusted) by default
- **No auth**: no registration, no token, free HTTP access

The project has a built-in EastMoney DataLoader at `backtest/loaders/eastmoney.py`. When backtesting, set `source: "eastmoney"` or rely on `source: "auto"` (EastMoney is the **#3 fallback** for A-shares, after mootdx and tushare).

## Quick Start

```python
from backtest.loaders.eastmoney import DataLoader

loader = DataLoader()

# Fetch daily K-lines
data = loader.fetch(
    codes=["600519.SH", "000001.SZ"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    interval="1D",
)
```

## Supported Intervals

| Interval | Description |
|----------|-------------|
| 1m | 1-minute bars |
| 5m | 5-minute bars |
| 15m | 15-minute bars |
| 30m | 30-minute bars |
| 1H (60m) | 60-minute bars |
| 1D | Daily bars |
| 1W | Weekly bars |
| 1M | Monthly bars |

## Notes

- Code format: `600519.SH` or `000001.SZ` (Shanghai/Shenzhen prefixed)
- EastMoney only supports A-shares (CN market), not HK or US stocks
- The API uses `secid` format internally (e.g., `1.600519` for Shanghai, `0.000001` for Shenzhen) — the DataLoader handles conversion automatically
- Data is forward-adjusted (前复权) by default
