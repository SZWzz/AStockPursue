---
name: coingecko
description: CoinGecko crypto market data — top coins by market cap, trending, global stats, exchange volumes. Free, no API key.
category: data-source
---
# CoinGecko

## Overview

CoinGecko provides free cryptocurrency market data including market cap rankings, trending coins, global market statistics, and exchange volumes. **No registration or API key required for basic usage.**

Note: CoinGecko does NOT provide OHLCV klines. For crypto OHLCV, use the `okx` or `ccxt` loaders. CoinGecko complements these with market-wide data (rankings, market cap, dominance).

The loader is at `backtest/loaders/coingecko.py`.

## Rate Limits

- Free tier: ~10-30 requests per minute
- No API key: shared rate limit across all users
- Consider adding a CoinGecko API key for higher limits

## Available Data

### 1. Top Coins by Market Cap
```python
from backtest.loaders.coingecko import DataLoader

loader = DataLoader()
top50 = loader.fetch_top_coins(limit=50)
# Returns: [{id, symbol, name, current_price, market_cap, market_cap_rank,
#            total_volume, price_change_percentage_24h, price_change_percentage_7d,
#            circulating_supply, ath, ath_change_percentage, ...}]
```

### 2. Trending Coins
```python
trending = loader.fetch_trending()
# Returns: [{id, symbol, name, market_cap_rank, price_btc, score}]
```

### 3. Global Market Stats
```python
global_stats = loader.fetch_global_stats()
# Returns: {active_cryptocurrencies, total_market_cap, total_volume,
#           market_cap_percentage, btc_dominance, eth_dominance,
#           market_cap_change_percentage_24h_usd}
```

### 4. Exchange Volumes
```python
exchanges = loader.fetch_exchanges(limit=20)
# Returns: [{id, name, country, trade_volume_24h_btc, trust_score,
#            trust_score_rank, year_established, url}]
```

## Integration with Other Crypto Sources

| Use Case | Best Source |
|----------|------------|
| OHLCV K-lines | okx / ccxt |
| Real-time ticker | okx |
| Market cap rankings | **coingecko** |
| Trending / hot coins | **coingecko** |
| Global market overview | **coingecko** |
| Exchange comparison | **coingecko** |
