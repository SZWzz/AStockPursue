---
name: baidu
category: data-source
description: Baidu Stock Trading (百度股市通) A-share K-line with built-in MA5/MA10/MA20 + concept/industry/region sector classification. Free, no API key.
---

# Baidu Stock Trading (百度股市通)

## Overview

Baidu Stock Trading provides **free A-share daily K-line data** via the Baidu Finance HTTP API. It has two unique features not found in other free sources:

1. **Built-in MA lines**: Each bar comes with MA5, MA10, MA20 pre-computed
2. **Sector classification**: Three-dimensional sector tags — **概念** (concept), **行业** (industry), **地域** (region)

No registration or API key required.

The project has a built-in Baidu DataLoader at `backtest/loaders/baidu.py`. When backtesting, set `source: "baidu"` or rely on `source: "auto"` (Baidu is the **#6 fallback** for A-shares).

## Quick Start

```python
from backtest.loaders.baidu import DataLoader

loader = DataLoader()

# Fetch daily K-lines
data = loader.fetch(
    codes=["600519.SH", "000001.SZ"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    interval="1D",
)

# Each bar includes MA5, MA10, MA20 columns in addition to OHLCV
```

## Sector Classification

Baidu's API returns three kinds of sector tags for each stock:
- **概念 (concept)**: e.g., 白酒, 人工智能, 新能源
- **行业 (industry)**: e.g., 食品饮料, 计算机, 电力设备
- **地域 (region)**: e.g., 贵州, 广东, 北京

## Limitations

- **Daily only**: Baidu does not support minute-level or weekly/monthly intervals. Use mootdx or eastmoney for those.
- **A-shares only**: No HK or US stock support
- **No historical depth limit documented**: test carefully for multi-year backtests
