---
name: data-routing
category: data-source
description: Data source selection decision tree. Load this skill BEFORE any backtest or data-fetching task to choose the best available data source.
---

## Data Source Overview

### OHLCV / K-line Sources

| Source | Markets | Auth Required | Network | Skill |
|--------|---------|---------------|---------|-------|
| tushare | A-shares, funds, futures, macro | Yes (`TUSHARE_TOKEN`) | China network | tushare |
| tencent | A-shares, HK stocks | No | Unrestricted | tencent |
| akshare | A-shares, US, HK, futures, macro, forex | No | Unrestricted | akshare |
| yfinance | US stocks, HK stocks, ETFs, indices | No | Needs Yahoo Finance access | yfinance |
| okx | Crypto (OKX exchange) | No | Needs okx.com access | okx-market |
| ccxt | Crypto (100+ exchanges) | No | Needs exchange access | ccxt |
| coingecko | Crypto (market cap, trending) | No | Unrestricted | coingecko |
| twelvedata | Global (all markets) | Yes (`TWELVE_DATA_API_KEY`) | Unrestricted | twelvedata |
| global_indices | Global stock indices | No | Needs Yahoo Finance access | global-indices |
| commodities | Precious metals, energy, industrial, agri | No | Needs Yahoo Finance access | commodities |

### Non-OHLCV Data Sources

| Source | Data Type | Auth Required | Skill |
|--------|-----------|---------------|-------|
| sentiment | VIX, DXY, Yield Curve, Fear & Greed | No | sentiment |
| fundamentals_enhanced | A-share/HK financial statements, PE/PB/ROE | No | fundamentals-enhanced |
| news | Financial news aggregation, economic calendar | No | news-aggregation |

## Decision Tree

### Backtest Scenario (writing config.json)

Use `source: "auto"` — the runner automatically routes by symbol pattern and falls back to alternative sources if the primary one is unavailable.

You do NOT need to specify a concrete data source in config.json unless the user explicitly asks for one.

### Analysis / Research Scenario (writing Python scripts)

1. Identify the market type from the user's request
2. Pick the source by priority:

**A-shares**: tushare (if TUSHARE_TOKEN is set) > tencent (fast, free) > twelvedata (if key set) > akshare (free fallback)

**US stocks**: yfinance > twelvedata (if key set) > finnhub (if key set) > akshare

**HK stocks**: yfinance > futu > tencent (fast, free) > twelvedata (if key set) > akshare

**Crypto OHLCV**: okx (single exchange) > ccxt (multi-exchange)

**Crypto market data**: coingecko (rankings, trending, global stats)

**Futures**: tushare > twelvedata > akshare

**Indices**: global_indices (via yfinance)

**Commodities**: commodities (via yfinance)

**Macro / economics**: akshare > tushare

**Forex**: akshare > twelvedata > yfinance

### Market Sentiment / Macro Analysis

Use the `market_sentiment` Agent tool or `SentimentFetcher` class directly:

- **VIX (fear gauge)**: yfinance ^VIX → akshare index_vix
- **DXY (USD strength)**: yfinance DX-Y.NYB → akshare currency_boc_sina
- **Yield Curve**: yfinance ^TNX (10Y) + estimated 2Y
- **Fear & Greed**: alternative.me API (crypto market)
- **Put/Call proxy**: VIX/VIX3M term structure

### Fundamentals Analysis

**A-shares**: tushare (financial statements, daily PE/PB) > fundamentals_enhanced (AKShare: PE-TTM, PB, PS, PEG, ROE, growth)

**HK stocks**: fundamentals_enhanced (AKShare: PE, PB, ROE, dividend yield) > twelvedata

**US stocks**: twelvedata (PE, PB, ROE, statements) > yfinance (basic info)

### News / Event Analysis

Use the `financial_news` Agent tool or `NewsFetcher` class:

- General market news: DuckDuckGo web search
- Sector-specific: targeted search queries
- Stock-specific: symbol + name search
- Economic calendar: template-based (US/CN major events)

### Availability Check

- **tushare**: check if `TUSHARE_TOKEN` environment variable exists
- **twelvedata**: check if `TWELVE_DATA_API_KEY` environment variable exists
- **tencent / coingecko / sentiment**: free, no auth, internet required
- **yfinance / okx / ccxt / akshare**: free but may have network restrictions
- If the user reports "connection timeout" or "cannot access", switch to the same-market fallback

## Symbol Format Reference

| Market | Format | Examples |
|--------|--------|---------|
| A-shares | `NNNNNN.SZ/SH/BJ` | 000001.SZ, 600000.SH |
| US stocks | `TICKER.US` | AAPL.US, MSFT.US |
| HK stocks | `NNN(N).HK` | 700.HK, 9988.HK |
| Crypto | `SYMBOL-USDT` | BTC-USDT, ETH-USDT |
| Futures | `XXNNNN.EXCHANGE` | CU2406.SHFE |
| Forex | `XXX/YYY` | USD/CNY, EUR/USD |
| Indices | `CODE` | SPX, DJI, IXIC, N225 |
| Commodities | `CODE` | XAUUSD, CL, HG |

## Fallback Chains (Runner Layer)

The backtest runner implements automatic fallback at the market level:

```
A_share:   tushare → tencent → twelvedata → akshare
US_equity: yfinance → twelvedata → finnhub → akshare
HK_equity: yfinance → futu → tencent → twelvedata → akshare
Crypto:    okx → ccxt → coingecko
Futures:   tushare → twelvedata → akshare
Forex:     akshare → twelvedata → yfinance
Index:     global_indices → yfinance
Commodity: commodities → yfinance
```

This is transparent to the user — they just see results.
