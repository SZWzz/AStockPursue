"""CNINFO (巨潮资讯) announcements — direct HTTP API (from 01.md).

Source: www.cninfo.com.cn/new/hisAnnouncement/query
Returns: A-share company disclosure announcements with title, type, date, url
"""

from __future__ import annotations

import logging

import requests

from .base import BaseNewsSource, normalize_article

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class CNINFOSource(BaseNewsSource):
    """巨潮公告 — direct HTTP to cninfo.com.cn."""

    name = "cninfo"
    label = "巨潮公告"
    category = "disclosure"

    def fetch_stock(self, symbol: str, limit: int = 10) -> list[dict]:
        """Fetch announcements for a specific stock."""
        raw = self._fetch(symbol, limit)
        normalized = self._normalize(raw)
        return normalized[:limit]

    def fetch_market(self, limit: int = 10) -> list[dict]:
        """No market-wide endpoint — would need to query major indices."""
        return []

    @staticmethod
    def _normalize_code(code: str) -> str:
        """Strip exchange suffix so we get a bare 6-digit code.

        "000001.SZ" → "000001", "600001.SH" → "600001", "430001.BJ" → "430001"
        """
        c = code.strip().upper()
        for suffix in (".SZ", ".SH", ".BJ", ".SS"):
            if c.endswith(suffix):
                c = c[:-3]
                break
        # Also handle "SH600001" / "SZ000001" prefix style
        if len(c) > 6:
            for prefix in ("SH", "SZ", "BJ"):
                if c.startswith(prefix) and c[2:].isdigit() and len(c[2:]) == 6:
                    c = c[2:]
                    break
        return c

    def _fetch(self, code: str, page_size: int = 30) -> list[dict]:
        """Raw fetch from CNINFO announcement query API."""
        try:
            code = self._normalize_code(code)

            # Construct orgId (CNINFO 2026 format)
            if code.startswith("6"):
                org_id = f"gssh0{code}"
            elif code.startswith(("8", "4")):
                org_id = f"gsbj0{code}"
            else:
                org_id = f"gssz0{code}"

            url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
            payload = {
                "stock": f"{code},{org_id}",
                "tabName": "fulltext",
                "pageSize": str(page_size),
                "pageNum": "1",
                "column": "",
                "category": "",
                "plate": "",
                "seDate": "",
                "searchkey": "",
                "secid": "",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            }
            headers = {
                "User-Agent": UA,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://www.cninfo.com.cn/new/disclosure",
                "Origin": "https://www.cninfo.com.cn",
            }
            r = requests.post(url, data=payload, headers=headers, timeout=15)
            d = r.json()

            items = d.get("announcements", []) or []
            return [
                {
                    "title": item.get("announcementTitle", ""),
                    "url": f"https://www.cninfo.com.cn/new/disclosure/detail?annoId={item.get('announcementId', '')}",
                    "summary": f"{item.get('announcementTypeName', '')}",
                    "time": str(item.get("announcementTime", "")),
                }
                for item in items
            ]
        except Exception as e:
            logger.debug("CNINFO announcement fetch failed for %s: %s", code, e)
            return []

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            a = normalize_article(r, self.name)
            if a:
                articles.append(a)
        return articles
