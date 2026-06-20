"""DataService gRPC implementation — bridges Python-only data loaders to Go."""

import logging
from datetime import datetime

import grpc
import pandas as pd

from src.gen import data_pb2, data_pb2_grpc, common_pb2

logger = logging.getLogger(__name__)


class DataServiceServicer(data_pb2_grpc.DataServiceServicer):
    """gRPC DataService wrapping Python-only data sources."""

    def __init__(self):
        self._loaders: dict[str, object] = {}

    def FetchBars(self, request, context):
        """Fetch historical bars from a named Python data source."""
        source = request.source
        symbol = request.symbol
        start = request.start_date
        end = request.end_date
        freq = request.frequency or "1d"

        logger.info("FetchBars: source=%s symbol=%s %s→%s freq=%s",
                    source, symbol, start, end, freq)

        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            end_dt = datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            return data_pb2.FetchBarsResponse(
                error=f"invalid date format: {start} / {end}",
            )

        try:
            df = self._fetch(source, symbol, start_dt, end_dt, freq)
        except Exception as exc:
            logger.exception("FetchBars failed for %s via %s", symbol, source)
            return data_pb2.FetchBarsResponse(error=str(exc))

        if df is None or df.empty:
            return data_pb2.FetchBarsResponse(error="no data returned")

        return data_pb2.FetchBarsResponse(
            bars=[self._row_to_bar(symbol, freq, ts, row) for ts, row in df.iterrows()],
        )

    def _fetch(self, source: str, symbol: str, start: datetime, end: datetime, freq: str) -> pd.DataFrame:
        """Dispatch to the appropriate Python loader."""
        if source == "mootdx":
            return self._fetch_mootdx(symbol, start, end, freq)
        raise ValueError(f"unknown data source: {source}")

    def _fetch_mootdx(self, symbol: str, start: datetime, end: datetime, freq: str) -> pd.DataFrame:
        """Fetch A-share bars via mootdx (通达信 TCP protocol)."""
        from mootdx.quotes import Quotes

        client = Quotes.factory(market="std", timeout=15)
        freq_map = {
            "1d": "day", "1w": "week", "1M": "mon",
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h",
        }
        mootdx_freq = freq_map.get(freq, "day")

        # Normalize symbol to plain 6-digit code
        code = symbol.strip().upper()
        for suffix in (".SH", ".SZ", ".BJ", ".SS"):
            if code.endswith(suffix):
                code = code[:-3]
        for prefix in ("SH", "SZ", "BJ"):
            if code.startswith(prefix) and len(code) > 2:
                code = code[2:]

        # mootdx expects SH/SZ prefix: 1=SH, 0=SZ
        if code.startswith("6"):
            market = 1
        else:
            market = 0

        # Fetch
        df = client.bars(symbol=code, frequency=mootdx_freq, start=start, end=end, market=market)
        if df is None or df.empty:
            return pd.DataFrame()

        # Standardize columns
        df = df.rename(columns={
            "open": "open", "high": "high", "low": "low", "close": "close",
            "volume": "volume",
        })
        # Ensure OHLCV columns exist
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = 0.0

        return df[["open", "high", "low", "close", "volume"]]

    @staticmethod
    def _row_to_bar(symbol: str, freq: str, ts, row) -> common_pb2.Bar:
        """Convert a DataFrame row to a protobuf Bar message."""
        return common_pb2.Bar(
            symbol=symbol,
            open=float(row.get("open", 0)),
            high=float(row.get("high", 0)),
            low=float(row.get("low", 0)),
            close=float(row.get("close", 0)),
            volume=int(row.get("volume", 0)),
            timestamp=int(ts.timestamp() * 1000),
            frequency=freq,
        )
