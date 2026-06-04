"""Risk manager — re-exports RiskPipeline from the unified trading package."""

from src.trading.risk_pipeline import RiskConfig, RiskPipeline  # noqa: F401

# Backward-compatible alias
RiskManager = RiskPipeline
