"""Shared gRPC client for DataService — used by Python callers to fetch data from Go.

This module provides a singleton gRPC client for the DataService, which bridges
Python-only data sources (mootdx, tushare, akshare, futu) to the Go core via gRPC.
Python callers that previously used ``backtest.loaders.registry`` directly should
import ``fetch_bars`` from here instead.
"""

from __future__ import annotations

import logging
from typing import Any

import grpc

from src.gen import data_pb2, data_pb2_grpc

logger = logging.getLogger(__name__)

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
        resp = client.FetchBars(req, timeout=30)
    except grpc.RpcError as exc:
        logger.debug("FetchBars gRPC call failed for %s: %s", symbol, exc)
        return []
    except Exception:
        logger.debug("FetchBars unexpected error for %s", symbol, exc_info=True)
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
