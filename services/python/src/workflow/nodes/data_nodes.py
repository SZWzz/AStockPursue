"""Data-loading nodes — StockUniverse and OHLCVLoader."""

from __future__ import annotations

import logging
from typing import List

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)

CSI300_CODES = [
    "000001.SZ", "000002.SZ", "000063.SZ", "000333.SZ", "000651.SZ", "000725.SZ",
    "000858.SZ", "002415.SZ", "002594.SZ", "300750.SZ", "600000.SH", "600009.SH",
    "600016.SH", "600028.SH", "600030.SH", "600036.SH", "600085.SH", "600104.SH",
    "600276.SH", "600309.SH", "600519.SH", "600585.SH", "600887.SH", "600900.SH",
    "601012.SH", "601088.SH", "601166.SH", "601288.SH", "601318.SH", "601398.SH",
    "601668.SH", "601857.SH", "601939.SH", "601988.SH", "603259.SH", "688981.SH",
]

CSI500_CODES = [
    "000009.SZ", "000021.SZ", "000027.SZ", "000039.SZ", "000060.SZ",
    "002008.SZ", "002028.SZ", "002044.SZ", "002074.SZ", "002091.SZ",
    "600004.SH", "600008.SH", "600021.SH", "600026.SH", "600029.SH",
    "600037.SH", "600038.SH", "600039.SH", "600050.SH", "600056.SH",
]

ACTIVE_A_SHARE = [
    "000001.SZ", "000002.SZ", "000858.SZ", "000333.SZ", "000651.SZ",
    "002594.SZ", "002415.SZ", "300750.SZ", "300059.SZ", "300124.SZ",
    "600519.SH", "600036.SH", "600030.SH", "600276.SH", "600887.SH",
    "601318.SH", "601166.SH", "601398.SH", "600900.SH", "600585.SH",
    "601012.SH", "603259.SH", "688981.SH", "688111.SH", "600809.SH",
]

UNIVERSES = {
    "csi300": {"label": "沪深300", "codes": CSI300_CODES},
    "csi500": {"label": "中证500", "codes": CSI500_CODES},
    "active_a_share": {"label": "活跃A股", "codes": ACTIVE_A_SHARE},
}


@register_node
class StockUniverseNode(BaseNode):
    node_type = "stock_universe"; category = "data"; label = "Stock Universe"
    description = "Choose a predefined stock pool (沪深300, 中证500, active A-shares) or input custom tickers"
    icon = "Layers"
    inputs: List[NodePort] = []
    outputs = [BaseNode.out_port("codes", PortType.STOCK_LIST)]
    config_schema = {
        "preset": {"title": "Universe", "type": "string", "enum": ["csi300", "csi500", "active_a_share", "custom"], "default": "csi300", "inline": True},
        "custom_codes": {"title": "Custom Tickers", "type": "stock_codes", "default": "", "description": "搜索股票代码，多个用逗号分隔"},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        preset = config.get("preset", "csi300")
        if preset == "custom" and config.get("custom_codes"):
            codes = [c.strip() for c in config["custom_codes"].split(",") if c.strip()]
        else:
            codes = list(UNIVERSES.get(preset, UNIVERSES["csi300"])["codes"])
        return {"codes": codes}


@register_node
class OHLCVLoaderNode(BaseNode):
    node_type = "ohlcv_loader"; category = "data"; label = "OHLCV Loader"
    description = "Load OHLCV data from cache or external APIs (DataStore fallback chain)"
    icon = "Database"; resource_profile = "io_bound"
    inputs = [BaseNode.in_port("codes", PortType.STOCK_LIST)]
    outputs = [BaseNode.out_port("ohlcv_data", PortType.DF_OHLCV)]
    config_schema = {
        "start_date": {"title": "Start Date", "type": "string", "default": "2024-01-01"},
        "end_date": {"title": "End Date", "type": "string", "default": "2025-12-31"},
        "interval": {"title": "Interval", "type": "string", "enum": ["1D", "1H", "4H", "1W"], "default": "1D", "inline": True},
        "source": {
            "title": "Data Source", "type": "string",
            "enum": ["auto", "mootdx", "tushare", "eastmoney", "tencent", "futu", "baidu",
                     "yfinance", "twelvedata", "finnhub", "akshare", "okx", "ccxt", "coingecko"],
            "default": "auto", "inline": True,
            "description": "auto = market-appropriate fallback chain; select a specific loader to force it",
        },
        "force_refresh": {
            "title": "Force Refresh", "type": "boolean", "default": False,
            "description": "Bypass cache and store, fetch directly from API",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        from backtest.data_store import get_data_store

        codes = inputs.get("codes", [])
        if isinstance(codes, pd.DataFrame):
            codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)
        if not codes:
            return {"ohlcv_data": {}}

        start = config.get("start_date", "2024-01-01")
        end = config.get("end_date", "2025-12-31")
        interval = config.get("interval", "1D")
        source = config.get("source", "auto")
        force_refresh = config.get("force_refresh", False)
        store = get_data_store()
        data_map = store.get_multi_ohlcv(
            codes=codes, start_date=start, end_date=end, interval=interval,
            source=source, force_refresh=force_refresh,
        )
        logger.info("OHLCV: %d/%d codes loaded (source=%s)", len(data_map), len(codes), source)
        return {"ohlcv_data": data_map}
