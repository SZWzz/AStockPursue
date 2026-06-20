"""Sina Finance Reports — balance sheet, income statement, cash flow.

Source: quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022
Returns: up to 20 periods of financial report data.

Usage:
    from backtest.loaders.sina_finance import SinaFinanceLoader
    loader = SinaFinanceLoader()
    lrb = loader.fetch_income_statement("600519")   # 利润表
    fzb = loader.fetch_balance_sheet("600519")      # 资产负债表
    llb = loader.fetch_cash_flow("600519")          # 现金流量表
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_REPORT_TYPES = {
    "lrb": "利润表",
    "fzb": "资产负债表",
    "llb": "现金流量表",
}


class SinaFinanceLoader:
    """Fetch financial statements from Sina Finance."""

    name = "sina_finance"
    BASE_URL = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"

    @staticmethod
    def _normalize_code(code: str) -> tuple[str, str]:
        """Normalize to (prefix, bare_code).

        "600519"      → ("sh", "600519")
        "000001.SZ"   → ("sz", "000001")
        "sh600519"    → ("sh", "600519")
        """
        c = code.strip().upper()
        # Strip suffix
        for suffix in (".SZ", ".SH", ".BJ", ".SS"):
            if c.endswith(suffix):
                c = c[:-3]
                break
        # Strip prefix
        for prefix in ("SH", "SZ", "BJ"):
            if c.startswith(prefix) and len(c) > 2:
                c = c[2:]
                break
        # Determine exchange prefix
        if c.startswith("6"):
            pfx = "sh"
        else:
            pfx = "sz"
        return pfx, c

    def _fetch(self, code: str, report_type: str) -> list[dict[str, Any]]:
        """Raw fetch from Sina finance API.

        Args:
            code: Stock code (6-digit or with suffix).
            report_type: "lrb" (利润表) / "fzb" (资产负债表) / "llb" (现金流量表).

        Returns:
            List of period dicts, newest first.
        """
        pfx, bare = self._normalize_code(code)
        paper_code = f"{pfx}{bare}"

        params = {
            "paperCode": paper_code,
            "source": report_type,
            "type": "0",
            "page": "1",
            "num": "20",
        }
        headers = {
            "User-Agent": UA,
            "Referer": "https://finance.sina.com.cn/",
        }

        try:
            r = requests.get(self.BASE_URL, params=params, headers=headers, timeout=15)
            d = r.json()
            result = d.get("result", {}).get("data", {})
            items = result.get(report_type, [])
            if isinstance(items, list):
                return items
            return []
        except Exception as e:
            logger.warning("Sina finance fetch failed for %s (%s): %s", code, report_type, e)
            return []

    def fetch_income_statement(self, code: str) -> list[dict[str, Any]]:
        """Fetch 利润表 (income statement)."""
        return self._fetch(code, "lrb")

    def fetch_balance_sheet(self, code: str) -> list[dict[str, Any]]:
        """Fetch 资产负债表 (balance sheet)."""
        return self._fetch(code, "fzb")

    def fetch_cash_flow(self, code: str) -> list[dict[str, Any]]:
        """Fetch 现金流量表 (cash flow statement)."""
        return self._fetch(code, "llb")

    def fetch_all(self, code: str) -> dict[str, list[dict[str, Any]]]:
        """Fetch all three statements.

        Returns:
            ``{"income_statement": [...], "balance_sheet": [...], "cash_flow": [...]}``
        """
        return {
            "income_statement": self.fetch_income_statement(code),
            "balance_sheet": self.fetch_balance_sheet(code),
            "cash_flow": self.fetch_cash_flow(code),
        }
