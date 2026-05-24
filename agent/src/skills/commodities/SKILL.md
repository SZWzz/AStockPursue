---
name: commodities
description: Commodity market data — precious metals, energy, industrial metals, agriculture. Free via yfinance.
category: data-source
---
# Commodities

## Overview

Provides OHLCV data and real-time snapshots for 20 major commodities across 4 categories. **Completely free via yfinance, no API key required.**

The project has a built-in Commodities DataLoader (`backtest/loaders/commodities.py`). For backtesting, use `source: "commodities"`.

## Available Commodities

### Precious Metals
| Code | Name | Ticker | Unit |
|------|------|--------|------|
| XAUUSD | Gold | GC=F | USD/oz |
| XAGUSD | Silver | SI=F | USD/oz |
| XPTUSD | Platinum | PL=F | USD/oz |
| XPDUSD | Palladium | PA=F | USD/oz |

### Energy
| Code | Name | Ticker | Unit |
|------|------|--------|------|
| CL | WTI Crude Oil | CL=F | USD/bbl |
| BZ | Brent Crude Oil | BZ=F | USD/bbl |
| NG | Natural Gas | NG=F | USD/MMBtu |
| HO | Heating Oil | HO=F | USD/gal |
| RB | RBOB Gasoline | RB=F | USD/gal |

### Industrial Metals
| Code | Name | Ticker | Unit |
|------|------|--------|------|
| HG | Copper | HG=F | USD/lb |
| ALI | Aluminum | ALI=F | USD/MT |
| ZNC | Zinc | ZNC=F | USD/MT |
| NI | Nickel | NI=F | USD/MT |

### Agriculture
| Code | Name | Ticker | Unit |
|------|------|--------|------|
| ZC | Corn | ZC=F | USC/bu |
| ZW | Wheat | ZW=F | USC/bu |
| ZS | Soybean | ZS=F | USC/bu |
| KC | Coffee | KC=F | USC/lb |
| CT | Cotton | CT=F | USC/lb |
| SB | Sugar | SB=F | USC/lb |

## Usage

### Python
```python
from backtest.loaders.commodities import DataLoader, list_commodities

# List by category
metals = list_commodities(category="precious_metal")
energy = list_commodities(category="energy")

# Fetch historical data
loader = DataLoader()
data = loader.fetch(
    codes=["XAUUSD", "XAGUSD", "CL"],
    start_date="2025-01-01",
    end_date="2025-12-31",
)

# Latest snapshot
latest = loader.fetch_latest(codes=["XAUUSD", "CL", "HG"])
```

### Agent Tool
Use `market_sentiment` with `indicator="commodities"` to get the latest commodity snapshot.

## Notes

- Commodity futures have expiration dates — yfinance automatically rolls to the front-month contract
- Volume data may be sparse for some contracts
- Use `interval="1D"` for daily data; intraday data is limited for futures
