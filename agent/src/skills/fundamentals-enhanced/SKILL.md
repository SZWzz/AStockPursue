---
name: fundamentals-enhanced
description: Enhanced fundamentals data — A-share and HK stock financial statements, PE/PB/ROE, growth metrics via AKShare (Eastmoney). Free, no API key.
category: data-source
---
# Enhanced Fundamentals

## Overview

Extends the existing Tushare-based fundamentals with AKShare (Eastmoney) data for:
- **A-shares**: Income statement, balance sheet, cash flow, PE/PB/PS/PEG, ROE, revenue/earnings growth
- **HK stocks**: PE/PB/ROE, dividend yield, revenue/earnings growth, market cap

This provides a free fallback when Tushare token is not available and adds HK stock fundamentals that Tushare does not cover.

The module is at `backtest/loaders/fundamentals_enhanced.py`.

## Usage

### A-share Fundamentals
```python
from backtest.loaders.fundamentals_enhanced import (
    fetch_a_share_profile,
    fetch_a_share_valuation,
    fetch_a_share_financials,
    fetch_a_share_all,
)

# Company profile (market cap, industry, shares outstanding)
profile = fetch_a_share_profile("600519")

# Valuation (PE, PB, PS, PEG)
valuation = fetch_a_share_valuation("600519")

# Financial statements + growth metrics
financials = fetch_a_share_financials("600519")

# All-in-one
complete = fetch_a_share_all("600519")
```

### HK Stock Fundamentals
```python
from backtest.loaders.fundamentals_enhanced import (
    fetch_hk_fundamentals,
    fetch_hk_company_profile,
)

# PE, PB, ROE, dividend yield, growth
fundamentals = fetch_hk_fundamentals("00700")

# Company profile
profile = fetch_hk_company_profile("00700")
```

## Data Fields

### A-share Profile
- `market_cap`, `float_market_cap` — 总市值 / 流通市值
- `total_shares`, `float_shares` — 总股本 / 流通股
- `industry`, `ipo_date` — 行业 / 上市时间

### A-share Valuation
- `pe_ratio` — 市盈率-TTM
- `pb_ratio` — 市净率-MRQ
- `ps_ratio` — 市销率-TTM
- `peg` — PEG

### A-share Financials
- `revenue_growth`, `earnings_growth` — YoY growth (%)
- `profit_margin` — 净利润率
- `debt_to_equity` — 资产负债率
- `current_ratio` — 流动比率
- `operating_cash_flow`, `free_cash_flow`
- `financial_statements`: income_statement, balance_sheet, cash_flow

### HK Stock Fundamentals
- `pe_ratio`, `pb_ratio`, `eps`, `roe`
- `profit_margin`, `dividend_yield`
- `revenue_growth`, `earnings_growth`
- `debt_to_equity`, `current_ratio`, `quick_ratio`

## Network Note

AKShare (Eastmoney) endpoints may be slow or fail from overseas servers. The `_bypass_proxy` context manager automatically clears proxy settings before calling AKShare to ensure direct connection to Chinese sites.

## Comparison with Tushare

| Feature | Tushare | Enhanced (AKShare) |
|---------|---------|-------------------|
| Auth | Token required | Free |
| A-share financials | Balance/income/cash flow | Balance/income/cash flow |
| A-share valuation | Daily PE/PB | PE-TTM/PB-MRQ/PS/PEG |
| HK stock data | No | PE/PB/ROE/dividend |
| Growth metrics | Limited | Revenue/earnings YoY |
| Network | Stable globally | May need CN network |
