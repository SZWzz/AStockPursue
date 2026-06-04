"""Sector mapping utility node — stock-to-sector classification.

Wraps get_bulk_sectors() from sector_mapper service.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class SectorMapNode(BaseNode):
    node_type = "sector_map"; category = "data"; label = "Sector Map"
    description = (
        "Classify stocks into Shenwan (申万) or GICS sectors. "
        "Returns sector labels and benchmark weights for each code."
    )
    icon = "Layers"
    inputs = [
        BaseNode.in_port("codes", PortType.STOCK_LIST,
                         description="Stock codes to classify"),
    ]
    outputs = [
        BaseNode.out_port("sector_data", PortType.PARAMS,
                          description="Sector mapping: {code: {sector, sub_sector, weight}}"),
    ]
    config_schema = {
        "classification": {
            "title": "Classification", "type": "string",
            "enum": ["sw", "gics"], "default": "sw",
        },
        "include_benchmark_weights": {
            "title": "Include Benchmark Weights", "type": "boolean", "default": False,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        codes = inputs.get("codes", [])
        if isinstance(codes, pd.DataFrame):
            codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)
        if not codes:
            return {"sector_data": {"error": "No stock codes provided"}}

        classification = config.get("classification", "sw")
        include_weights = config.get("include_benchmark_weights", False)

        try:
            from src.services.sector_mapper import get_bulk_sectors, get_sector_benchmark_weights

            sectors = get_bulk_sectors(codes, classification=classification)

            result: Dict[str, Any] = {}
            for code in codes:
                sec = sectors.get(code, {})
                result[code] = {
                    "sector": sec.get("sector", "Unknown"),
                    "sub_sector": sec.get("sub_sector", ""),
                }

            if include_weights:
                try:
                    benchmark = get_sector_benchmark_weights(classification=classification)
                    result["_benchmark_weights"] = benchmark
                except Exception:
                    result["_benchmark_weights"] = {"error": "Unavailable"}

            # ── Sector distribution summary ───────────────────────────────────
            dist: Dict[str, int] = {}
            for code, info in result.items():
                if code.startswith("_"):
                    continue
                sec = info.get("sector", "Unknown")
                dist[sec] = dist.get(sec, 0) + 1

            result["_summary"] = {
                "n_codes": len(codes) - (1 if "_benchmark_weights" in result else 0),
                "n_sectors": len(dist),
                "distribution": dist,
                "classification": classification,
            }

            logger.info("SectorMap: %d codes → %d sectors (%s)", len(codes), len(dist), classification)
            return {"sector_data": result}

        except ImportError:
            return {"sector_data": {"error": "Sector mapper not available", "codes": list(codes)}}
