#!/usr/bin/env python3
"""A-stock data preload — download HS300 daily bars and precompute factors."""
import argparse
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("init_data")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "cache" / "preload"


# ---- Stock list ----
def _code_to_symbol(code):
    """Convert 6-digit code to symbol string: 6xxxxx→SH, 0xxxxx/3xxxxx→SZ."""
    code = str(code).zfill(6)
    if code.startswith("6"):
        return f"{code}.SH"
    return f"{code}.SZ"


def _get_index_symbols(index_code):
    """Get constituent stocks for a given index code via akshare."""
    import akshare as ak

    df = ak.index_stock_cons(symbol=index_code)
    symbols = [_code_to_symbol(row["品种代码"]) for _, row in df.iterrows()]
    return symbols


def get_hs300_symbols():
    """Get HS300 constituent stocks via akshare."""
    return _get_index_symbols("000300")


def get_zz500_symbols():
    """Get ZZ500 constituent stocks via akshare."""
    return _get_index_symbols("000905")


# ---- Download ----
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds base — multiplied by 2^(retry-1)


def download_one(symbol, start, end):
    """Download daily bars for one stock with retry. Returns DataFrame or None."""
    import akshare as ak

    code = symbol.split(".")[0]
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            if df is None or df.empty:
                log.warning("Empty data for %s", symbol)
                return None
            df = df.rename(
                columns={
                    "日期": "timestamp",
                    "开盘": "open",
                    "收盘": "close",
                    "最高": "high",
                    "最低": "low",
                    "成交量": "volume",
                    "成交额": "amount",
                }
            )
            df["symbol"] = symbol
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df[["symbol", "timestamp", "open", "high", "low", "close", "volume", "amount"]]
        except Exception:
            if attempt < MAX_RETRIES:
                delay = RETRY_BACKOFF * (2 ** (attempt - 1))
                log.debug("Retry %d/%d for %s in %.1fs", attempt, MAX_RETRIES, symbol, delay)
                time.sleep(delay)
            else:
                log.warning("Download failed for %s after %d attempts", symbol, MAX_RETRIES)
                return None
    return None


def download_all(symbols, start, end, workers=10):
    """Download daily bars for all symbols in parallel with staggered submission."""
    all_data = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {}
        for i, s in enumerate(symbols):
            futures[ex.submit(download_one, s, start, end)] = s
            if i < len(symbols) - 1:
                time.sleep(0.05)  # stagger submissions to avoid hammering the server
        for f in tqdm(as_completed(futures), total=len(symbols), desc="Downloading"):
            result = f.result()
            if result is not None:
                all_data.append(result)
    if not all_data:
        return pd.DataFrame()
    return pd.concat(all_data, ignore_index=True)


# ---- Factors ----
def compute_factors(df):
    """Precompute 20 basic factors for all stocks.

    Factors computed:
    01 ret_1d             — 1-day return
    02 ret_5d             — 5-day return
    03 ret_20d            — 20-day return
    04 volatility_20d     — 20-day rolling volatility
    05 turnover_5d        — 5-day mean volume change ratio
    06 rsi_14             — 14-day RSI
    07 ma_5               — close / 5-day MA
    08 ma_20              — close / 20-day MA
    09 ma_60              — close / 60-day MA
    10 amplitude_20d      — 20-day rolling avg amplitude
    11 volume_ratio_5d    — volume / 5-day avg volume
    12 max_drawdown_20d   — drawdown from 20-day high
    13 up_days_ratio_20d  — fraction of up days in last 20
    14 gap_ratio          — (open - prev_close) / prev_close
    15 close_position_20d — close position within 20-day range
    16 bb_position        — Bollinger Band position (20,2)
    17 macd               — MACD line (12,26,9)
    18 macd_signal        — MACD signal line
    19 atr_14             — 14-day Average True Range (pct)
    20 momentum_10d       — 10-day momentum (close — close_10d_ago)/close_10d_ago
    """
    results = []
    for sym, grp in tqdm(df.groupby("symbol"), desc="Computing factors"):
        g = grp.sort_values("timestamp").set_index("timestamp")
        close = g["close"]
        volume = g["volume"]
        high, low = g["high"], g["low"]
        opn = g["open"]

        factors = pd.DataFrame(index=g.index)

        # 01-03: Returns
        factors["ret_1d"] = close.pct_change()
        factors["ret_5d"] = close.pct_change(5)
        factors["ret_20d"] = close.pct_change(20)

        # 04: Volatility
        factors["volatility_20d"] = factors["ret_1d"].rolling(20).std()

        # 05: Turnover change (5-day avg volume ratio)
        vol_ma5 = volume.rolling(5).mean()
        factors["turnover_5d"] = vol_ma5 / vol_ma5.shift(1)

        # 06: RSI-14
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta).clip(lower=0).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        factors["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

        # 07-09: MA ratios (close / MA)
        factors["ma_5"] = close / close.rolling(5).mean()
        factors["ma_20"] = close / close.rolling(20).mean()
        factors["ma_60"] = close / close.rolling(60).mean()

        # 10: Amplitude (average (high-low)/close over 20 days)
        factors["amplitude_20d"] = ((high - low) / close).rolling(20).mean()

        # 11: Volume ratio (volume / 5-day avg volume)
        factors["volume_ratio_5d"] = volume / vol_ma5

        # 12: Max drawdown from 20-day high
        roll_max = close.rolling(20).max()
        factors["max_drawdown_20d"] = (close - roll_max) / roll_max

        # 13: Up days ratio over 20 days
        factors["up_days_ratio_20d"] = (close > close.shift(1)).rolling(20).sum() / 20.0

        # 14: Gap ratio (open vs prev close)
        factors["gap_ratio"] = (opn - close.shift(1)) / close.shift(1)

        # 15: Close position in 20-day range (0–1)
        rmin_20 = close.rolling(20).min()
        rmax_20 = close.rolling(20).max()
        factors["close_position_20d"] = (close - rmin_20) / (rmax_20 - rmin_20)

        # 16: Bollinger Band position (20, 2)
        ma_20_val = close.rolling(20).mean()
        std_20 = close.rolling(20).std()
        factors["bb_position"] = (close - ma_20_val) / (2.0 * std_20)

        # 17-18: MACD (12, 26, 9)
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        factors["macd"] = macd_line
        factors["macd_signal"] = macd_line.ewm(span=9, adjust=False).mean()

        # 19: ATR-14 (as percentage of close)
        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr_14 = tr.rolling(14).mean()
        factors["atr_14"] = atr_14 / close

        # 20: 10-day momentum
        factors["momentum_10d"] = (close - close.shift(10)) / close.shift(10)

        factors["symbol"] = sym
        results.append(factors.reset_index())

    if not results:
        return pd.DataFrame()
    out = pd.concat(results, ignore_index=True)
    # Ensure column ordering: symbol, timestamp, then factors
    cols = ["symbol", "timestamp"] + [c for c in out.columns if c not in ("symbol", "timestamp")]
    return out[cols]


# ---- Main ----
def main():
    parser = argparse.ArgumentParser(description="Download A-stock data and precompute factors")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--index", default="hs300", choices=["hs300", "zz500"])
    parser.add_argument("--limit", type=int, default=0, help="Limit number of symbols (0=all)")
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--output", default=str(OUTPUT_DIR))
    parser.add_argument("--skip-factors", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    log.info("Getting %s symbols...", args.index)
    if args.index == "hs300":
        symbols = get_hs300_symbols()
    else:
        symbols = get_zz500_symbols()

    if args.limit:
        symbols = symbols[: args.limit]
    log.info("Got %d symbols", len(symbols))

    # Compute date range
    today = pd.Timestamp.today()
    start = (today - pd.DateOffset(years=args.years)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    log.info("Date range: %s — %s", start, end)

    df = download_all(symbols, start, end, args.workers)
    if df.empty:
        log.error("No data downloaded!")
        sys.exit(1)

    log.info("Writing Parquet by year...")
    for year, grp in df.groupby(df["timestamp"].dt.year):
        fpath = out_dir / f"bars_1d_{year}.parquet"
        grp.to_parquet(fpath, index=False)
        log.info("  %s  %d bars", fpath.name, len(grp))

    symbols_df = pd.DataFrame({"symbol": symbols})
    symbols_df.to_csv(out_dir / "symbols.csv", index=False)
    log.info("  symbols.csv  %d symbols", len(symbols))

    if not args.skip_factors:
        factors = compute_factors(df)
        fpath = out_dir / "factors_basic.parquet"
        factors.to_parquet(fpath, index=False)
        log.info("  %s  %d rows", fpath.name, len(factors))

    elapsed = time.time() - t0
    log.info("Done! %d stocks, %d bars, %.1fs", len(symbols), len(df), elapsed)
    log.info("Output: %s", out_dir)
    print(f"\n{len(symbols)} stocks · {len(df):,} bars · {elapsed:.0f}s · {out_dir}")


if __name__ == "__main__":
    main()
