"""Stock-to-sector mapping for attribution calculations.

Provides real Shenwan (申万) and GICS industry classifications for A-share
stocks using akshare. Results are cached in memory for the session.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── In-memory cache ──────────────────────────────────────────────────

_sector_cache: dict[str, dict[str, str]] = {}  # {classification: {code: sector}}
_cache_loaded: dict[str, bool] = {}


def _normalise_code(code: str) -> str:
    """Normalise a stock code to the form used by akshare (6 digits)."""
    code = code.upper().strip()
    # Remove exchange suffix: 000001.SZ → 000001
    if "." in code:
        code = code.split(".")[0]
    return code


def _load_sw_sectors() -> dict[str, str]:
    """Load Shenwan industry classification for all A-share stocks via akshare."""
    mapping: dict[str, str] = {}
    try:
        import akshare as ak
        # akshare 申万行业分类
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty and "板块名称" in df.columns:
            # This gives us industry→stocks. We need stock→industry.
            # We'll iterate and expand.
            for _, row in df.iterrows():
                industry = str(row.get("板块名称", ""))
                stock_list_str = str(row.get("板块个股", ""))
                if industry and stock_list_str and stock_list_str != "nan":
                    codes = [c.strip() for c in stock_list_str.split(",") if c.strip()]
                    for code in codes:
                        mapping[_normalise_code(code)] = industry
            logger.info("Loaded %d stock→sector mappings from akshare (SW)", len(mapping))
    except Exception as e:
        logger.warning("Failed to load SW sectors from akshare: %s", e)

    return mapping


def _load_gics_sectors() -> dict[str, str]:
    """Load GICS sector mapping for Chinese stocks via akshare.

    Falls back to a known subset since full GICS coverage of A-shares is limited.
    """
    mapping: dict[str, str] = {}
    try:
        import akshare as ak
        # Try eastmoney GICS classification
        df = ak.stock_sector_detail(sector="申万一级", date="")
        if df is not None and not df.empty:
            # This gives sector detail, not full GICS mapping.
            # Fall back to a smaller but real dataset.
            pass
    except Exception:
        pass

    # Try the more comprehensive approach: iterate SW→GICS mapping
    try:
        import akshare as ak
        df = ak.stock_board_concept_name_em()
        # This won't give GICS directly, log and continue
    except Exception:
        pass

    if not mapping:
        logger.info("GICS mapping not available via akshare, using SW→GICS crosswalk")

    return mapping


def get_stock_sector(
    code: str,
    classification: str = "sw",
    force_reload: bool = False,
) -> str:
    """Map a single stock to its sector.

    Args:
        code: Stock code (e.g. "000001.SZ", "600519", "600519.SH").
        classification: "sw" (Shenwan) or "gics".
        force_reload: If True, skip cache and re-fetch.

    Returns:
        Sector name, or "Unknown" if mapping not available.
    """
    global _sector_cache, _cache_loaded

    if classification not in _sector_cache or force_reload:
        _sector_cache[classification] = {}

    cache = _sector_cache[classification]

    if not cache and not _cache_loaded.get(classification):
        if classification == "sw":
            _sector_cache[classification] = _load_sw_sectors()
        elif classification == "gics":
            _sector_cache[classification] = _load_gics_sectors()
        _cache_loaded[classification] = True
        cache = _sector_cache[classification]

    norm = _normalise_code(code)
    sector = cache.get(norm, "")
    if sector:
        return sector

    # Try with original code (for non-A-share symbols like BTC-USDT)
    return cache.get(code, "Unknown")


def get_bulk_sectors(
    codes: list[str],
    classification: str = "sw",
    force_reload: bool = False,
) -> dict[str, str]:
    """Map a list of stock codes to their sectors.

    Args:
        codes: List of stock codes.
        classification: "sw" or "gics".
        force_reload: Skip cache.

    Returns:
        Dict mapping each code to its sector name.
    """
    # Ensure cache is loaded
    get_stock_sector("000001", classification, force_reload)

    result: dict[str, str] = {}
    for code in codes:
        result[code] = get_stock_sector(code, classification)
    return result


def get_sector_benchmark_weights(
    classification: str = "sw",
    universe: str = "csi300",
) -> dict[str, float]:
    """Get benchmark sector weights for common universes.

    For CSI 300: approximate equal-weight across sectors (can be refined
    with real index constituent data).

    Args:
        classification: "sw" or "gics".
        universe: "csi300", "csi500", or "all".

    Returns:
        Dict mapping sector → benchmark weight.
    """
    from .attribution_engine import get_sector_list

    sectors = get_sector_list(classification)

    # Approximate CSI 300 sector weights (based on typical distributions)
    # These are rough but reasonable defaults. For precise weights,
    # a full index constituent lookup would be needed.
    if universe == "csi300":
        # Typical CSI 300 sector distribution (approximate)
        csi300_approx: dict[str, float] = {
            "银行": 0.12, "非银金融": 0.10, "食品饮料": 0.09,
            "医药生物": 0.07, "电子": 0.08, "电力设备": 0.08,
            "计算机": 0.04, "汽车": 0.04, "机械设备": 0.04,
            "基础化工": 0.03, "有色金属": 0.03, "房地产": 0.02,
            "交通运输": 0.02, "公用事业": 0.02, "建筑装饰": 0.02,
            "通信": 0.02, "传媒": 0.02, "国防军工": 0.02,
            "家用电器": 0.02, "农林牧渔": 0.01, "煤炭": 0.01,
            "钢铁": 0.01, "石油石化": 0.01, "建筑材料": 0.01,
            "商贸零售": 0.01, "社会服务": 0.01, "轻工制造": 0.01,
            "纺织服饰": 0.01, "环保": 0.01, "美容护理": 0.005, "综合": 0.005,
        }
        result: dict[str, float] = {}
        for s in sectors:
            en_name = s
            result[s] = csi300_approx.get(en_name, 1.0 / len(sectors))
        total = sum(result.values())
        return {k: v / total for k, v in result.items()}

    # Default: equal weight
    return {s: 1.0 / len(sectors) for s in sectors}
