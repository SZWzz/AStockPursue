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
        if source == "tushare":
            return self._fetch_tushare(symbol, start, end, freq)
        if source == "akshare":
            return self._fetch_akshare(symbol, start, end, freq)
        if source == "futu":
            return self._fetch_futu(symbol, start, end, freq)
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


    def _fetch_tushare(self, symbol: str, start: datetime, end: datetime, freq: str) -> pd.DataFrame:
        """Fetch A-share bars via Tushare API."""
        import os
        token = os.environ.get("TUSHARE_TOKEN", "")
        if not token:
            raise RuntimeError("TUSHARE_TOKEN environment variable not set")
        import tushare as ts
        ts.set_token(token)
        api = ts.pro_api()
        sd = start.strftime("%Y%m%d")
        ed = end.strftime("%Y%m%d")
        # Normalize code: strip .SH/.SZ suffix
        code = symbol.strip().upper()
        for suffix in (".SH", ".SZ", ".BJ", ".SS"):
            if code.endswith(suffix):
                code = code[:-3]
        # Add suffix for tushare (SH/SZ)
        if code.startswith("6"):
            ts_code = code + ".SH"
        else:
            ts_code = code + ".SZ"
        df = api.daily(ts_code=ts_code, start_date=sd, end_date=ed, adj="qfq")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.sort_values("trade_date")
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.set_index("trade_date")
        df = df.rename(columns={"vol": "volume"})
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df[["open", "high", "low", "close", "volume"]].dropna(subset=["open", "high", "low", "close"])

    def _fetch_akshare(self, symbol: str, start: datetime, end: datetime, freq: str) -> pd.DataFrame:
        """Fetch bars via AKShare (multi-market: A-share, US, HK, ETF, forex)."""
        import akshare as ak
        code = symbol.strip().upper()
        # Remove suffix
        for suffix in (".SH", ".SZ", ".SS", ".HK"):
            if code.endswith(suffix):
                code = code[:-3]
        s = start.strftime("%Y%m%d")
        e = end.strftime("%Y%m%d")
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=s, end_date=e, adjust="qfq")
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.rename(columns={"日期": "trade_date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume"})
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.set_index("trade_date")
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df[["open", "high", "low", "close", "volume"]]
        except Exception:
            return pd.DataFrame()

    def _fetch_futu(self, symbol: str, start: datetime, end: datetime, freq: str) -> pd.DataFrame:
        """Fetch bars via Futu OpenAPI (requires FutuOpenD running locally)."""
        import os
        host = os.environ.get("FUTU_HOST", "127.0.0.1")
        port = int(os.environ.get("FUTU_PORT", "11111"))
        try:
            import futu as ft
        except ImportError:
            raise RuntimeError("futu-api not installed. pip install futu-api")
        code = symbol.strip().upper()
        # Add market prefix for Futu
        if code.startswith("6"):
            ft_code = "SH." + code
        else:
            ft_code = "SZ." + code
        freq_map = {"1d": ft.KLType.K_DAY, "1w": ft.KLType.K_WEEK, "1M": ft.KLType.K_MON,
                     "1m": ft.KLType.K_1M, "5m": ft.KLType.K_5M, "15m": ft.KLType.K_15M,
                     "30m": ft.KLType.K_30M, "1h": ft.KLType.K_60M}
        ktype = freq_map.get(freq, ft.KLType.K_DAY)
        ctx = ft.OpenQuoteContext(host=host, port=port)
        try:
            ret, df = ctx.request_history_kline(ft_code, ktype=ktype, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
            if ret != 0 or df is None or df.empty:
                return pd.DataFrame()
            df = df.rename(columns={"time_key": "trade_date"})
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.set_index("trade_date")
            df = df[["open", "high", "low", "close", "volume"]]
            df = df.apply(pd.to_numeric, errors="coerce")
            return df.dropna(subset=["open", "high", "low", "close"])
        finally:
            ctx.close()

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
