"""Shared gRPC client for DataService — used by Python callers to fetch data from Go.

This module provides a singleton gRPC client for the DataService, which bridges
Python-only data sources (mootdx, tushare, akshare, futu) to the Go core via gRPC.
Python callers that previously used ``backtest.loaders.registry`` directly should
import ``fetch_bars`` from here instead.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import grpc

from src.gen import data_pb2, data_pb2_grpc

logger = logging.getLogger(__name__)


def _is_transient_grpc_error(exc: Exception) -> bool:
    """判断 gRPC 错误是否可重试（网络抖动 vs 业务错误）。"""
    if isinstance(exc, grpc.RpcError):
        code = exc.code()
        return code in (
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.DEADLINE_EXCEEDED,
            grpc.StatusCode.RESOURCE_EXHAUSTED,
            grpc.StatusCode.INTERNAL,  # 可能是临时性内部错误
        )
    return True  # 非 gRPC 异常（连接错误）也重试


def _retry_with_backoff(
    fn,
    max_retries: int = 3,
    base_delay: float = 0.1,
) -> Any:
    """带线性退避 + jitter 的重试调用。

    Args:
        fn: 无参可调用对象（已经部分应用的 gRPC 调用）。
        max_retries: 最大重试次数（总调用次数 = max_retries + 1）。
        base_delay: 基础延迟秒数，第 N 次重试延迟 = base_delay * N + jitter。

    Returns:
        fn() 的返回值。

    Raises:
        最后一次尝试的异常（如果所有重试都失败）。
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            if not _is_transient_grpc_error(exc):
                raise
            jitter = random.uniform(0, base_delay * (attempt + 1) * 0.5)
            delay = base_delay * (attempt + 1) + jitter
            logger.debug(
                "Retry attempt %d/%d after %.2fs: %s",
                attempt + 1, max_retries, delay, exc,
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


_data_client: data_pb2_grpc.DataServiceStub | None = None


def get_data_client() -> data_pb2_grpc.DataServiceStub:
    """Return a singleton DataService gRPC client.

    The client connects to the Python gRPC server on localhost:8902.
    Callers should use :func:`fetch_bars` instead of calling this directly.
    """
    global _data_client
    if _data_client is None:
        channel = grpc.insecure_channel("localhost:8902")
        _data_client = data_pb2_grpc.DataServiceStub(channel)
    return _data_client


def fetch_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    source: str = "auto",
    frequency: str = "1d",
) -> list[dict[str, Any]]:
    """Fetch OHLCV bars via gRPC DataService.

    Args:
        symbol: Symbol code (e.g. ``600519.SH``, ``AAPL.US``).
        start_date: Start date as ``YYYY-MM-DD``.
        end_date: End date as ``YYYY-MM-DD``.
        source: Data source name (``"mootdx"``, ``"tushare"``, ``"akshare"``,
            ``"futu"``, or ``"auto"``).  When ``"auto"``, the DataService
            tries sources in its configured fallback order.
        frequency: Bar frequency (``"1d"``, ``"1h"``, etc.).  Default ``"1d"``.

    Returns:
        A list of dicts, each with keys ``symbol``, ``open``, ``high``, ``low``,
        ``close``, ``volume``, ``timestamp``.  Returns an empty list on failure
        or when no data is available.
    """
    client = get_data_client()
    req = data_pb2.FetchBarsRequest(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        source=source,
        frequency=frequency,
    )
    try:
        resp = _retry_with_backoff(
            lambda: client.FetchBars(req, timeout=30),
            max_retries=3,
            base_delay=0.1,
        )
    except Exception as exc:
        logger.debug("FetchBars gRPC call failed for %s after retries: %s", symbol, exc)
        return []

    if resp.error:
        logger.debug("FetchBars returned error for %s: %s", symbol, resp.error)
        return []

    bars: list[dict[str, Any]] = []
    for bar in resp.bars:
        bars.append({
            "symbol": bar.symbol,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "timestamp": bar.timestamp,
        })
    return bars


def fetch_bars_bulk(
    symbols: list[str],
    start_date: str,
    end_date: str,
    source: str = "auto",
    frequency: str = "1d",
) -> dict[str, "pd.DataFrame"]:
    """Fetch OHLCV bars for multiple symbols, return symbol→DataFrame map.

    This is a convenience wrapper around :func:`fetch_bars`.  It makes one
    gRPC call per symbol and assembles the results into a ``data_map``
    suitable for backtesting and factor computation.

    Args:
        symbols: List of symbol codes.
        start_date / end_date / source / frequency: Forwarded to
            :func:`fetch_bars` for each symbol.

    Returns:
        ``{symbol: DataFrame}``.  Symbols with no data are omitted.
        Returns an empty dict if *all* symbols fail.
    """
    import pandas as pd

    data_map: dict[str, "pd.DataFrame"] = {}
    for sym in symbols:
        bars = fetch_bars(
            symbol=sym,
            start_date=start_date,
            end_date=end_date,
            source=source,
            frequency=frequency,
        )
        if not bars:
            if len(symbols) > 1:
                time.sleep(0.05)  # 50ms 间隔，避免重试风暴
            continue
        df = pd.DataFrame(bars)
        if "timestamp" in df.columns:
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        data_map[sym] = df

    return data_map
