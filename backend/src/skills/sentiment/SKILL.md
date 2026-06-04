---
name: sentiment
description: Market sentiment indicators — VIX, VXN, GVZ, DXY, Yield Curve, Fear & Greed Index, Put/Call Ratio proxy. Free data from yfinance and alternative.me.
category: data-source
---
# Market Sentiment

## Overview

Market sentiment indicators provide a macro-level view of market fear, greed, and risk appetite. All data is free — VIX/DXY/yield curve come from yfinance, Fear & Greed from alternative.me.

The sentiment fetcher is at `backtest/loaders/sentiment.py` and is also exposed as an Agent tool (`market_sentiment`).

## Available Indicators

### 1. VIX — CBOE Volatility Index (^VIX)
The "fear gauge" — measures expected S&P 500 volatility over the next 30 days.

| Range | Level | Meaning |
|-------|-------|---------|
| <12 | very_low | Extreme optimism |
| 12-20 | low | Market stable |
| 20-25 | moderate | Normal level |
| 25-30 | high | Market concern |
| >30 | very_high | Market panic |

### 2. VXN — NASDAQ Volatility Index (^VXN)
Tech-sector specific volatility measure.

### 3. GVZ — Gold Volatility Index (^GVZ)
Gold market volatility — rising GVZ signals increased safe-haven demand.

### 4. DXY — US Dollar Index (DX-Y.NYB)
Measures USD strength against a basket of major currencies.

| Range | Level | Impact |
|-------|-------|--------|
| >105 | strong | Bearish commodities/EM |
| 100-105 | moderate_strong | Watch capital flows |
| 95-100 | neutral | Market balanced |
| 90-95 | moderate_weak | Bullish risk assets |
| <90 | weak | Bullish gold/commodities |

### 5. Yield Curve — 10Y-2Y Spread (^TNX)
Inverted curve (negative spread) is a classic recession signal.

| Spread | Level | Signal |
|--------|-------|--------|
| <-0.5 | deeply_inverted | Strong recession signal |
| -0.5-0 | inverted | Recession warning |
| 0-0.5 | flat | Economic slowdown |
| 0.5-1.5 | normal | Healthy economy |
| >1.5 | steep | Economic expansion |

### 6. Fear & Greed Index (alternative.me)
Crypto market sentiment: 0 = Extreme Fear, 100 = Extreme Greed.
Updates every 24 hours.

### 7. Put/Call Ratio Proxy (VIX/VIX3M term structure)
VIX term structure as a proxy for options market sentiment.

| Ratio | Level | Signal |
|-------|-------|--------|
| >1.15 | high_fear | Backwardation — high short-term fear |
| 1.0-1.15 | elevated | Slight backwardation |
| 0.9-1.0 | normal | Stable |
| <0.8 | extreme_complacency | Watch for reversal |

## Usage

### Python
```python
from backtest.loaders.sentiment import SentimentFetcher

fetcher = SentimentFetcher()

# Individual indicators
vix = fetcher.fetch_vix()
dxy = fetcher.fetch_dxy()
fgi = fetcher.fetch_fear_greed()

# All indicators at once
all_data = fetcher.fetch_all()
```

### Agent Tool
The `market_sentiment` tool is available to the AI agent:
- "当前市场情绪如何？" → agent calls `market_sentiment`
- "VIX现在多少？" → agent calls `market_sentiment` with indicator="vix"

## Fallbacks
- VIX: yfinance → akshare (index_vix)
- DXY: yfinance → akshare (currency_boc_sina)
- Fear & Greed: alternative.me only
