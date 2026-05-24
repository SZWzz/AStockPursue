---
name: global-indices
description: Global stock index data — S&P 500, DJI, NASDAQ, DAX, FTSE, Nikkei 225, Hang Seng, KOSPI, and more. Free via yfinance.
category: data-source
---
# Global Indices

## Overview

Provides OHLCV data and real-time snapshots for 15+ major global stock indices via yfinance. **Completely free, no API key required.**

The project has a built-in GlobalIndices DataLoader (`backtest/loaders/global_indices.py`). For backtesting, use `source: "global_indices"`.

## Available Indices

### US
| Code | Name | Ticker |
|------|------|--------|
| SPX | S&P 500 | ^GSPC |
| DJI | Dow Jones Industrial | ^DJI |
| IXIC | NASDAQ Composite | ^IXIC |
| NDX | NASDAQ 100 | ^NDX |
| RUT | Russell 2000 | ^RUT |

### Europe
| Code | Name | Ticker |
|------|------|--------|
| DAX | DAX 40 | ^GDAXI |
| FTSE | FTSE 100 | ^FTSE |
| CAC | CAC 40 | ^FCHI |
| STOXX | Euro STOXX 50 | ^STOXX50E |

### Asia
| Code | Name | Ticker |
|------|------|--------|
| N225 | Nikkei 225 | ^N225 |
| HSI | Hang Seng Index | ^HSI |
| KOSPI | KOSPI | ^KS11 |
| ASX | ASX 200 | ^AXJO |
| SENSEX | BSE SENSEX | ^BSESN |

### China (offshore ETFs)
| Code | Name | Ticker |
|------|------|--------|
| CSI300 | CSI 300 ETF | 510300.SS |
| SZ50 | SSE 50 ETF | 510050.SS |

## Usage

### Python
```python
from backtest.loaders.global_indices import DataLoader, list_indices, get_index_info

# List all indices
all_idx = list_indices()

# List by region
us_idx = list_indices(region="US")

# Fetch historical data
loader = DataLoader()
data = loader.fetch(
    codes=["SPX", "DJI", "IXIC"],
    start_date="2025-01-01",
    end_date="2025-12-31",
    interval="1D",
)

# Latest snapshot
latest = loader.fetch_latest()  # All indices
us_latest = loader.fetch_latest(codes=["SPX", "DJI", "NDX"])
```

### Agent Tool
Use the `market_sentiment` tool with `indicator="global_indices"` to get the latest index snapshot.

## Column Format

Returned OHLCV DataFrame follows the standard schema:
- `trade_date` (index), `open`, `high`, `low`, `close`, `volume`
