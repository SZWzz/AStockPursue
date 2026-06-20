"""Enhanced fundamentals loader: A-share and HK stock financial statements.

Extends the existing Tushare fundamentals with AKShare-based data for:
  - A-share: income statement, balance sheet, cash flow, PE/PB/PS/PEG/ROE/market cap
  - HK stock: PE/PB/ROE/dividend yield/market cap via Eastmoney

This provides a free fallback when Tushare token is not available, and adds
HK stock fundamentals that Tushare does not cover.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger(__name__)

_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


@contextmanager
def _bypass_proxy() -> Generator[None, None, None]:
    """Temporarily clear proxy env vars so AkShare can reach Chinese sites directly."""
    saved = {}
    for key in _PROXY_KEYS:
        val = os.environ.pop(key, None)
        if val is not None:
            saved[key] = val
    try:
        yield
    finally:
        for key, val in saved.items():
            os.environ[key] = val


def _float_clean(x: Any) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        v = float(x)
        return None if (v != v or v == float("inf") or v == float("-inf")) else v
    except (TypeError, ValueError):
        return None


def _pct_change(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    if curr is None or prev is None or prev == 0:
        return None
    return round((curr - prev) / abs(prev) * 100, 2)


def _safe_iloc(df, row: int, col: str) -> Optional[float]:
    try:
        if df is None or getattr(df, "empty", True):
            return None
        if col not in df.columns:
            return None
        return _float_clean(df.iloc[row][col])
    except Exception:
        return None


# =====================================================================
# A-share fundamentals
# =====================================================================

def fetch_a_share_profile(symbol: str) -> Dict[str, Any]:
    """Fetch A-share company profile via AKShare (Eastmoney).

    Args:
        symbol: 6-digit A-share code (e.g. '600519' or '000001').
    """
    sym = str(symbol).zfill(6)
    result: Dict[str, Any] = {}
    try:
        import akshare as ak
        with _bypass_proxy():
            df = ak.stock_individual_info_em(symbol=sym)
    except Exception as e:
        logger.debug("stock_individual_info_em failed for %s: %s", sym, e)
        return result

    if df is None or getattr(df, "empty", True) or len(df.columns) < 2:
        return result

    kcol, vcol = df.columns[0], df.columns[1]
    info: Dict[str, str] = {}
    for _, row in df.iterrows():
        try:
            k = str(row[kcol]).strip()
            if k:
                info[k] = str(row[vcol])
        except Exception:
            continue

    result["market_cap"] = _float_clean(info.get("总市值"))
    result["float_market_cap"] = _float_clean(info.get("流通市值"))
    result["total_shares"] = _float_clean(info.get("总股本"))
    result["float_shares"] = _float_clean(info.get("流通股"))
    if info.get("行业"):
        result["industry"] = info["行业"]
    if info.get("上市时间"):
        result["ipo_date"] = info["上市时间"]
    result["source"] = "akshare_em"
    return result


def fetch_a_share_valuation(symbol: str) -> Dict[str, Any]:
    """Fetch A-share PE/PB/PS/PEG via AKShare Eastmoney.

    Args:
        symbol: 6-digit A-share code.
    """
    sym = str(symbol).zfill(6)
    result: Dict[str, Any] = {"source": "akshare_em"}

    # Build Eastmoney symbol: SH600519 / SZ000001
    em_sym = ("SH" if sym.startswith("6") else "SZ") + sym

    try:
        import akshare as ak
        with _bypass_proxy():
            vdf = ak.stock_zh_valuation_comparison_em(symbol=em_sym)
    except Exception as e:
        logger.debug("stock_zh_valuation_comparison_em failed for %s: %s", em_sym, e)
        return result

    if vdf is None or vdf.empty or "代码" not in vdf.columns:
        return result

    hit = vdf[vdf["代码"].astype(str).str.replace(".0", "", regex=False).str.zfill(6) == sym]
    if hit.empty:
        return result

    r = hit.iloc[0]
    result["pe_ratio"] = _float_clean(r.get("市盈率-TTM"))
    result["pb_ratio"] = _float_clean(r.get("市净率-MRQ"))
    result["ps_ratio"] = _float_clean(r.get("市销率-TTM"))
    result["peg"] = _float_clean(r.get("PEG"))
    return result


def fetch_a_share_financials(symbol: str) -> Dict[str, Any]:
    """Fetch A-share financial statements (income, balance, cash flow) via AKShare.

    Args:
        symbol: 6-digit A-share code.
    """
    sym = str(symbol).zfill(6)
    result: Dict[str, Any] = {}
    statements: Dict[str, Any] = {}

    try:
        import akshare as ak

        with _bypass_proxy():
            # Income statement
            try:
                profit_df = ak.stock_profit_sheet_by_report_em(symbol=sym)
                if profit_df is not None and not profit_df.empty:
                    r = profit_df.iloc[0]
                    rev_curr = _safe_iloc(profit_df, 0, "营业总收入")
                    rev_prev = _safe_iloc(profit_df, 1, "营业总收入")
                    result["revenue_growth"] = _pct_change(rev_curr, rev_prev)

                    net_curr = _safe_iloc(profit_df, 0, "净利润")
                    net_prev = _safe_iloc(profit_df, 1, "净利润")
                    result["earnings_growth"] = _pct_change(net_curr, net_prev)

                    if rev_curr and rev_curr > 0 and net_curr is not None:
                        result["profit_margin"] = round(net_curr / rev_curr * 100, 2)

                    statements["income_statement"] = {
                        "total_revenue": rev_curr,
                        "operating_income": _safe_iloc(profit_df, 0, "营业利润"),
                        "net_income": net_curr,
                    }
            except Exception as e:
                logger.debug("A-share profit sheet failed for %s: %s", sym, e)

            # Balance sheet
            try:
                balance_df = ak.stock_balance_sheet_by_report_em(symbol=sym)
                if balance_df is not None and not balance_df.empty:
                    total_debt = _safe_iloc(balance_df, 0, "负债合计")
                    total_equity = _safe_iloc(balance_df, 0, "股东权益合计") or _safe_iloc(balance_df, 0, "所有者权益合计")
                    if total_debt is not None and total_equity and total_equity > 0:
                        result["debt_to_equity"] = round(total_debt / total_equity, 4)

                    current_assets = _safe_iloc(balance_df, 0, "流动资产合计")
                    current_liab = _safe_iloc(balance_df, 0, "流动负债合计")
                    if current_assets is not None and current_liab and current_liab > 0:
                        result["current_ratio"] = round(current_assets / current_liab, 4)

                    statements["balance_sheet"] = {
                        "total_assets": _safe_iloc(balance_df, 0, "资产总计"),
                        "total_liabilities": total_debt,
                        "stockholders_equity": total_equity,
                        "current_assets": current_assets,
                        "current_liabilities": current_liab,
                    }
            except Exception as e:
                logger.debug("A-share balance sheet failed for %s: %s", sym, e)

            # Cash flow
            try:
                cashflow_df = ak.stock_cash_flow_sheet_by_report_em(symbol=sym)
                if cashflow_df is not None and not cashflow_df.empty:
                    op_cf = _safe_iloc(cashflow_df, 0, "经营活动产生的现金流量净额")
                    capex = _safe_iloc(cashflow_df, 0, "购建固定资产、无形资产和其他长期资产支付的现金")
                    if op_cf is not None:
                        result["operating_cash_flow"] = op_cf
                        if capex is not None:
                            result["free_cash_flow"] = round(op_cf - abs(capex), 2)
                    result["investing_cash_flow"] = _safe_iloc(cashflow_df, 0, "投资活动产生的现金流量净额")
                    result["financing_cash_flow"] = _safe_iloc(cashflow_df, 0, "筹资活动产生的现金流量净额")

                    statements["cash_flow"] = {
                        "operating_cash_flow": op_cf,
                        "investing_cash_flow": result["investing_cash_flow"],
                        "financing_cash_flow": result["financing_cash_flow"],
                        "free_cash_flow": result.get("free_cash_flow"),
                    }
            except Exception as e:
                logger.debug("A-share cash flow failed for %s: %s", sym, e)

    except ImportError:
        logger.warning("akshare not installed, A-share financial data unavailable")

    if statements:
        result["financial_statements"] = statements
    return result


def fetch_a_share_all(symbol: str) -> Dict[str, Any]:
    """Fetch complete A-share fundamentals: profile + valuation + financial statements."""
    result: Dict[str, Any] = {}
    result.update(fetch_a_share_profile(symbol))
    result.update(fetch_a_share_valuation(symbol))
    financials = fetch_a_share_financials(symbol)
    # Merge carefully: financial_statements is nested
    if "financial_statements" in financials:
        result["financial_statements"] = financials.pop("financial_statements")
    result.update(financials)
    return result


# =====================================================================
# HK stock fundamentals
# =====================================================================

def fetch_hk_fundamentals(symbol: str) -> Dict[str, Any]:
    """Fetch HK stock fundamentals via AKShare (Eastmoney).

    Args:
        symbol: HK stock code as digits (e.g. '00700', '9988').
    """
    sym = str(symbol).zfill(5)
    result: Dict[str, Any] = {"source": "akshare_em"}

    try:
        import akshare as ak
        with _bypass_proxy():
            df = ak.stock_hk_financial_indicator_em(symbol=sym)
    except Exception as e:
        logger.debug("stock_hk_financial_indicator_em failed for %s: %s", sym, e)
        return result

    if df is None or df.empty:
        return result

    r = df.iloc[0]
    result["pe_ratio"] = _float_clean(r.get("市盈率"))
    result["pb_ratio"] = _float_clean(r.get("市净率"))
    result["eps"] = _float_clean(r.get("基本每股收益(元)"))
    result["roe"] = _float_clean(r.get("股东权益回报率(%)"))
    result["profit_margin"] = _float_clean(r.get("销售净利率(%)"))
    mcap = _float_clean(r.get("总市值(港元)")) or _float_clean(r.get("港股市值(港元)"))
    if mcap is not None:
        result["market_cap"] = mcap
    result["dividend_yield"] = _float_clean(r.get("股息率TTM(%)"))

    if len(df) > 1:
        prev = df.iloc[1]
        rev_curr = _float_clean(r.get("营业总收入(元)")) or _float_clean(r.get("营业收入(元)"))
        rev_prev = _float_clean(prev.get("营业总收入(元)")) or _float_clean(prev.get("营业收入(元)"))
        result["revenue_growth"] = _pct_change(rev_curr, rev_prev)

        net_curr = _float_clean(r.get("净利润(元)"))
        net_prev = _float_clean(prev.get("净利润(元)"))
        result["earnings_growth"] = _pct_change(net_curr, net_prev)

    de_pct = _float_clean(r.get("资产负债率(%)"))
    if de_pct is not None and de_pct < 100:
        result["debt_to_equity"] = round(de_pct / (100 - de_pct), 4)

    result["current_ratio"] = _float_clean(r.get("流动比率"))
    result["quick_ratio"] = _float_clean(r.get("速动比率"))

    return result


def fetch_hk_company_profile(symbol: str) -> Dict[str, Any]:
    """Fetch HK stock company profile via AKShare."""
    sym = str(symbol).zfill(5)
    result: Dict[str, Any] = {}
    try:
        import akshare as ak
        with _bypass_proxy():
            df = ak.stock_hk_company_profile_em(symbol=sym)
    except Exception as e:
        logger.debug("stock_hk_company_profile_em failed for %s: %s", sym, e)
        return result

    if df is None or df.empty:
        return result

    r = df.iloc[0]
    for key, col in (
        ("industry", "所属行业"),
        ("ipo_date", "公司成立日期"),
        ("website", "公司网址"),
        ("full_name", "公司名称"),
    ):
        v = r.get(col)
        if v is not None and str(v).strip():
            result[key] = str(v).strip()
    return result
