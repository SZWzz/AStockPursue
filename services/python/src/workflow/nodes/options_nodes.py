"""Options pricing node — Black-Scholes, Binomial Tree, implied volatility, Greeks.

Wraps OptionsPricingEngine for use in workflow pipelines.
"""

from __future__ import annotations

import logging
from typing import List

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class OptionsNode(BaseNode):
    node_type = "options_pricing"; category = "analysis"; label = "Options Pricing"
    description = (
        "Price options using Black-Scholes or Binomial Tree models. "
        "Also computes implied volatility, Greeks, and volatility surface."
    )
    icon = "CircleDollarSign"
    inputs: List[NodePort] = []
    outputs = [
        BaseNode.out_port("options_result", PortType.PARAMS,
                          description="Pricing result with price + Greeks"),
    ]
    config_schema = {
        "method": {
            "title": "Pricing Method", "type": "string",
            "enum": ["black_scholes", "binomial", "implied_vol", "vol_surface", "greeks"],
            "default": "black_scholes",
        },
        "S": {
            "title": "Spot Price (S)", "type": "number", "default": 100.0,
            "minimum": 0.01,
        },
        "K": {
            "title": "Strike Price (K)", "type": "number", "default": 100.0,
            "minimum": 0.01,
        },
        "T": {
            "title": "Time to Expiry (years)", "type": "number", "default": 0.25,
            "minimum": 0.001, "maximum": 10.0,
        },
        "r": {
            "title": "Risk-Free Rate", "type": "number", "default": 0.03,
            "minimum": 0.0, "maximum": 0.5,
        },
        "sigma": {
            "title": "Volatility (σ)", "type": "number", "default": 0.25,
            "minimum": 0.01, "maximum": 5.0,
        },
        "option_type": {
            "title": "Option Type", "type": "string",
            "enum": ["call", "put"], "default": "call",
        },
        "n_steps": {
            "title": "Binomial Steps", "type": "integer", "default": 100,
            "minimum": 10, "maximum": 1000,
        },
        "market_price": {
            "title": "Market Price (for IV)", "type": "number", "default": 5.0,
            "description": "Required for implied volatility calculation",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        method = config.get("method", "black_scholes")

        try:
            from src.services.options_pricing import OptionsPricingEngine
            engine = OptionsPricingEngine()

            S = float(config.get("S", 100))
            K = float(config.get("K", 100))
            T = float(config.get("T", 0.25))
            r = float(config.get("r", 0.03))
            sigma = float(config.get("sigma", 0.25))
            opt_type = config.get("option_type", "call")

            if method == "black_scholes":
                result = engine.black_scholes(S, K, T, r, sigma, opt_type)

            elif method == "binomial":
                n_steps = int(config.get("n_steps", 100))
                price = engine.binomial_tree(S, K, T, r, sigma, n_steps, opt_type)
                result = {"price": price, "method": "binomial_tree", "n_steps": n_steps}

            elif method == "implied_vol":
                market_price = float(config.get("market_price", 5.0))
                iv = engine.implied_volatility(S, K, T, r, market_price, opt_type)
                result = {"implied_vol": iv} if iv is not None else {"error": "IV did not converge"}

            elif method == "vol_surface":
                surface = engine.generate_vol_surface(S, r)
                result = {"points": [s.model_dump() if hasattr(s, "model_dump") else s for s in surface], "spot": S}

            elif method == "greeks":
                result = engine.black_scholes(S, K, T, r, sigma, opt_type)
            else:
                result = {"error": f"Unknown method: {method}"}

            logger.info("Options: method=%s S=%.2f K=%.2f", method, S, K)
            return {"options_result": result.model_dump() if hasattr(result, "model_dump") else result}

        except ImportError:
            # Fallback: manual Black-Scholes
            from math import exp, log, sqrt
            from scipy.stats import norm

            def bs_price(S, K, T, r, sigma, opt_type):
                d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
                d2 = d1 - sigma * sqrt(T)
                if opt_type == "call":
                    return S * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
                return K * exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

            try:
                price = bs_price(S, K, T, r, sigma, opt_type)
                return {"options_result": {
                    "price": round(price, 4),
                    "S": S, "K": K, "T": T, "r": r, "sigma": sigma,
                    "option_type": opt_type, "method": "black_scholes_fallback",
                }}
            except Exception as e:
                return {"options_result": {"error": str(e)}}
