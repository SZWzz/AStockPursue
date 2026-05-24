---
name: tencent
description: Tencent Finance real-time quotes and K-line data for A-shares and HK stocks. Free, no API key, millisecond-level real-time data. Stable alternative when Tushare/AKShare/yfinance are rate-limited.
category: data-source
---
# Tencent Finance

## Overview

Tencent Finance provides free, real-time stock quotes and historical K-line data for China A-shares (Shanghai/Shenzhen) and Hong Kong stocks. **No registration or API key required.**

- **Real-time quotes**: `qt.gtimg.cn` — millisecond-level price updates
- **K-line data**: `web.ifzq.gtimg.cn/appstock/app/fqkline/get` — daily/weekly/monthly

The project has a built-in Tencent DataLoader (`backtest/loaders/tencent.py`). When backtesting, set `source: "tencent"` or rely on `source: "auto"` (Tencent is the #2 fallback for A-shares after Tushare, #3 for HK stocks after yfinance/Futu).

## Quick Start

The DataLoader handles code normalization automatically. No separate setup needed.

```python
from backtest.loaders.tencent import DataLoader, normalize_cn_code, normalize_hk_code

loader = DataLoader()

# Fetch historical K-lines
data = loader.fetch(
    codes=["000001.SZ", "600519.SH"],
    start_date="2025-01-01",
    end_date="2025-12-31",
    interval="1D",
)

# Fetch real-time quote
quote = loader.fetch_quote("000001.SZ")
# Returns: {symbol, name, last, change, change_percent, open, high, low,
#           previous_close, volume, amount, turnover, pe, market_cap}
```

## Code Format

| Market | Project Format | Tencent Format | Example |
|--------|---------------|----------------|---------|
| A-share (Shanghai) | `600519.SH` | `sh600519` | 贵州茅台 |
| A-share (Shenzhen) | `000001.SZ` | `sz000001` | 平安银行 |
| A-share (Beijing) | `430047.BJ` | `bj430047` | |
| HK stock | `700.HK` | `hk00700` | 腾讯控股 |

## Real-time Quote Fields

The quote endpoint returns ~50 fields. Key fields:

| Index | Field | Description |
|-------|-------|-------------|
| 1 | name | Stock name (GBK-decoded) |
| 2 | symbol | Exchange-tagged code |
| 3 | last | Current price |
| 4 | prev_close | Previous close |
| 5 | open | Today's open |
| 6 | volume | Volume (手) |
| 33 | high | Today's high |
| 34 | low | Today's low |
| 37 | amount | Turnover (万元) |
| 38 | turnover_rate | Turnover rate (%) |
| 39 | pe | P/E ratio |
| 45 | market_cap | Total market cap (亿元) |

## K-line Adjustment Modes

| Mode | Param | Description |
|------|-------|-------------|
| qfq | 前复权 | Forward-adjusted (default in AStockPursue) |
| hfq | 后复权 | Backward-adjusted |
| (none) | 不复权 | Unadjusted |

## Limitations

- **No minute-level K-lines**: Tencent fqkline supports day/week/month only. Use AKShare for minute bars.
- **GBK encoding**: Responses are GBK-encoded. The DataLoader handles this automatically.
- **No US stocks**: Tencent only covers CN/HK markets.

## Fallback Position

In the auto-routing chain, Tencent is positioned as a fast, free fallback:
- **A-shares**: tushare → **tencent** → twelvedata → akshare
- **HK stocks**: yfinance → futu → **tencent** → twelvedata → akshare
