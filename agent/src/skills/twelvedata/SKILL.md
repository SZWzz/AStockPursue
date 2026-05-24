---
name: twelvedata
description: Twelve Data global market API — OHLCV for stocks/forex/crypto/indices, fundamentals, financial statements. Paid with 800 free credits/day.
category: data-source
---
# Twelve Data

## Overview

Twelve Data (https://twelvedata.com) provides high-quality global market data. The free tier gives 800 credits/day (~80-100 API calls).

**Requires API key**: Set `TWELVE_DATA_API_KEY` environment variable.

The loader is at `backtest/loaders/twelvedata.py`.

## Setup

```bash
export TWELVE_DATA_API_KEY="your_api_key_here"
```

Register at https://twelvedata.com to get a free API key.

## Supported Markets

| Market | Exchange Codes | Data Types |
|--------|---------------|------------|
| A-shares | SHH (Shanghai), SHZ (Shenzhen) | OHLCV, statistics, profile |
| US stocks | NYSE, NASDAQ | OHLCV, statistics, profile, statements |
| HK stocks | HKG | OHLCV, statistics, profile |
| Forex | (auto) | OHLCV |
| Crypto | (auto) | OHLCV |
| Indices | (auto) | OHLCV |
| Commodities | (auto) | OHLCV |

## Usage

### OHLCV Data
```python
from backtest.loaders.twelvedata import DataLoader

loader = DataLoader()

# Check availability
if loader.is_available():
    data = loader.fetch(
        codes=["AAPL.US", "600519.SH"],
        start_date="2025-01-01",
        end_date="2025-12-31",
        interval="1D",
    )
```

### Fundamentals
```python
loader = DataLoader()

# Valuation statistics
stats = loader.fetch_statistics("AAPL.US")
# Returns: {market_cap, pe_ratio, pb_ratio, ps_ratio, peg, roe, roa,
#           profit_margin, eps, debt_to_equity, dividend_yield, beta, ...}

# Company profile
profile = loader.fetch_profile("AAPL.US")
# Returns: {name, industry, sector, website, description, employees, country}

# Financial statements
statements = loader.fetch_financial_statements("AAPL.US")
# Returns: {income_statement: {...}, balance_sheet: {...}, cash_flow: {...}}
```

## Credit Usage

Each API call consumes 1 credit from your daily quota:
- `/time_series` (OHLCV): 1 credit per symbol/day
- `/statistics`: 1 credit per symbol
- `/profile`: 1 credit per symbol
- `/income_statement` + `/balance_sheet` + `/cash_flow`: 3 credits total

Free tier: 800 credits/day. A full fundamentals fetch for one stock costs ~5 credits.

## Fallback Position

In the auto-routing chain, Twelve Data is positioned as a mid-tier option:
- **A-shares**: tushare → tencent → **twelvedata** → akshare
- **US stocks**: yfinance → **twelvedata** → akshare
- **HK stocks**: yfinance → futu → tencent → **twelvedata** → akshare

It is only used when `TWELVE_DATA_API_KEY` is set AND higher-priority sources fail.
