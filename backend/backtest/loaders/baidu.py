"""Baidu Stock Trading (百度股市通) data loader.

Free HTTP API, no auth.  Provides:
  - K-line with built-in MA5/MA10/MA20 (baidu auto-calculates)
  - 3D stock block classification: industry (申万) / concept / region
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from backtest.loaders.base import validate_date_range
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

_BAIDU_KLINE_URL = "https://finance.pae.baidu.com/selfselect/getstockquotation"
_BAIDU_BLOCK_URL = "https://finance.pae.baidu.com/api/getrelatedblock"


def _normalize_code(symbol: str) -> str:
    """Return 6-digit plain code for Baidu API."""
    s = (symbol or "").strip().upper()
    for suffix in (".SH", ".SZ", ".BJ", ".SS"):
        if s.endswith(suffix):
            s = s[:-3]
            break
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix) and len(s) > 2:
            s = s[2:]
            break
    return s.strip()


@register
class DataLoader:
    """Baidu Stock Trading OHLCV loader (free HTTP, no auth, K-line with MA)."""

    name = "baidu"
    markets = {"a_share"}
    requires_auth = False

    def is_available(self) -> bool:
        # [P2-06 fix] Check actual API reachability instead of just import.
        # Previously always returned True when requests was installed, even
        # when the Baidu Finance API was unreachable, breaking the fallback
        # chain in _fetch_auto().
        try:
            import requests
            # Quick connectivity check to the API endpoint with short timeout
            resp = requests.head(
                "https://finance.pae.baidu.com/selfselect/openapi/v2",
                timeout=2.0,
            )
            # Accept any response (even 404 means the server is reachable)
            return True
        except Exception:
            return False

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        # Baidu only supports daily kline right now
        if interval not in ("1D", "day", "daily"):
            logger.debug("Baidu only supports 1D interval, got %s", interval)
            return {}

        validate_date_range(start_date, end_date)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        }

        result: Dict[str, pd.DataFrame] = {}

        for code in codes:
            try:
                plain = _normalize_code(code)
                params = {
                    "all": "1",
                    "isIndex": "false",
                    "isBk": "false",
                    "isBlock": "false",
                    "isFutures": "false",
                    "isStock": "true",
                    "newFormat": "1",
                    "group": "quotation_kline_ab",
                    "finClientType": "pc",
                    "code": plain,
                    "ktype": "1",  # daily
                }
                r = requests.get(_BAIDU_KLINE_URL, params=params, headers=headers, timeout=10)
                d = r.json()
                result_data = d.get("Result", {})
                md = result_data.get("newMarketData", {})
                keys = md.get("keys", [])
                rows_raw = md.get("marketData", "")

                if not keys or not rows_raw:
                    logger.debug("Baidu returned empty for %s", code)
                    continue

                # Build DataFrame from semicolon-separated rows
                all_rows = []
                for line in rows_raw.split(";"):
                    values = line.split(",")
                    if len(values) >= len(keys):
                        row = {}
                        for i, k in enumerate(keys):
                            row[k] = values[i]
                        all_rows.append(row)

                if not all_rows:
                    continue

                df = pd.DataFrame(all_rows)

                # Find time column
                time_col = None
                for c in df.columns:
                    if "time" in c.lower():
                        time_col = c
                        break

                if time_col is None:
                    logger.debug("Baidu: no time column in response for %s", code)
                    continue

                df[time_col] = pd.to_datetime(df[time_col])
                df = df.set_index(time_col).sort_index()

                # Map Baidu column names to standard OHLCV
                # Baidu fields: time, open, close, high, low, volume, amount,
                # ma5avgprice, ma10avgprice, ma20avgprice, ...
                col_map = {}
                for col in df.columns:
                    cl = col.lower()
                    if cl in ("open", "high", "low", "close", "volume"):
                        col_map[col] = cl
                df = df.rename(columns=col_map)

                # Detect truncation: Baidu's `all=1` should return full history,
                # but some server deployments may cap the response.  If the
                # earliest bar is well after the requested start_date, warn so
                # the runner can fall back to another source.
                raw_earliest = df.index.min()
                requested_start = pd.Timestamp(start_date)
                # [P2-01 fix] Reduced threshold from 60 to 10 days.  60 days was
                # far too permissive — a source returning 59 days late passed
                # silently, effectively hiding data truncation.  10 days is a
                # reasonable tolerance for weekends/holidays.
                if raw_earliest is not pd.NaT and raw_earliest > requested_start + pd.Timedelta(days=10):
                    logger.warning(
                        "Baidu data for %s appears truncated: "
                        "requested %s, earliest available bar is %s "
                        "(gap=%d days). Baidu free API may not retain full history. "
                        "Consider using eastmoney, tencent, tushare, or akshare for longer histories.",
                        code, start_date, raw_earliest.strftime("%Y-%m-%d"),
                    )

                # Filter date range
                df = df.loc[start_date:end_date]

                # Keep OHLCV + optional MA columns
                keep_cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
                if not keep_cols:
                    continue

                result_df = df[keep_cols].astype("float64")

                # Optionally attach MA columns if available
                for ma_col in ("ma5avgprice", "ma10avgprice", "ma20avgprice"):
                    if ma_col in df.columns:
                        result_df[ma_col] = df[ma_col].astype("float64")

                if not result_df.empty:
                    result[code] = result_df

            except Exception as exc:
                logger.warning("Baidu fetch failed for %s: %s", code, exc)
                continue

        return result

    # ── Concept block API (not part of DataLoaderProtocol, utility method) ──

    def fetch_concept_blocks(self, code: str) -> dict:
        """Get 3D stock block classification for *code*.

        Returns:
            dict with keys ``industry``, ``concept``, ``region``, ``concept_tags``.
        """
        plain = _normalize_code(code)
        headers = {
            "Host": "finance.pae.baidu.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0",
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        }
        params = {
            "code": plain,
            "market": "ab",
            "typeCode": "all",
            "finClientType": "pc",
        }

        try:
            r = requests.get(_BAIDU_BLOCK_URL, params=params, headers=headers, timeout=10)
            d = r.json()
            if str(d.get("ResultCode", -1)) != "0":
                logger.debug("Baidu block API error for %s: %s", code, d)
                return {"industry": [], "concept": [], "region": [], "concept_tags": []}

            result: dict = {"industry": [], "concept": [], "region": [], "concept_tags": []}
            for block in d.get("Result", []):
                block_type = block.get("type", "")
                for item in block.get("list", []):
                    entry = {
                        "name": item.get("name", ""),
                        "change_pct": item.get("increase", ""),
                        "desc": item.get("desc", ""),
                    }
                    if "行业" in block_type:
                        result["industry"].append(entry)
                    elif "概念" in block_type:
                        result["concept"].append(entry)
                        result["concept_tags"].append(item.get("name", ""))
                    elif "地域" in block_type:
                        result["region"].append(entry)
            return result
        except Exception as exc:
            logger.warning("Baidu concept blocks failed for %s: %s", code, exc)
            return {"industry": [], "concept": [], "region": [], "concept_tags": []}
