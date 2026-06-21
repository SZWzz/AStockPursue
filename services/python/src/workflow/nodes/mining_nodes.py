"""Factor mining node — GP evolution for alpha factor discovery.

Wraps GPEvolution.run() as a workflow node.  GP evolution is a long-running
computation; progress is logged but not streamed (future: SSE progress events).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import PortType

logger = logging.getLogger(__name__)


@register_node
class GPEvolutionNode(BaseNode):
    node_type = "gp_evolution"; category = "alpha"; label = "GP Evolution"
    description = (
        "Run Genetic Programming evolution to discover alpha factors. "
        "Uses hybrid initialisation (30% skeletons + 40% mutations + 30% random), "
        "composite fitness (IC × cost × orthogonality × stability), "
        "and FDR correction (Benjamini-Yekutieli) for correlated candidates."
    )
    icon = "Microscope"
    resource_profile = "cpu_bound"
    inputs = [
        BaseNode.in_port("codes", PortType.STOCK_LIST,
                         description="Stock codes for the GP universe"),
        BaseNode.in_port("ohlcv_data", PortType.DF_OHLCV, required=False,
                         description="OHLCV data — GP loads its own data if not provided"),
    ]
    outputs = [
        BaseNode.out_port("best_factors", PortType.FACTOR_RESULT,
                          description="Best discovered factors with IC and formula"),
        BaseNode.out_port("generation_log", PortType.PARAMS,
                          description="Per-generation fitness stats"),
    ]
    config_schema = {
        "population_size": {
            "title": "Population Size", "type": "integer", "default": 100,
            "minimum": 10, "maximum": 500,
        },
        "generations": {
            "title": "Generations", "type": "integer", "default": 50,
            "minimum": 5, "maximum": 200,
        },
        "train_start": {
            "title": "Train Start", "type": "string", "default": "2024-01-01",
        },
        "train_end": {
            "title": "Train End", "type": "string", "default": "2025-12-31",
        },
        "test_start": {
            "title": "Test Start", "type": "string", "default": "2025-01-01",
        },
        "test_end": {
            "title": "Test End", "type": "string", "default": "2025-12-31",
        },
        "tournament_size": {
            "title": "Tournament Size", "type": "integer", "default": 7,
            "minimum": 2, "maximum": 20,
        },
        "crossover_prob": {
            "title": "Crossover Prob", "type": "number", "default": 0.7,
            "minimum": 0.0, "maximum": 1.0,
        },
        "mutation_prob": {
            "title": "Mutation Prob", "type": "number", "default": 0.2,
            "minimum": 0.0, "maximum": 1.0,
        },
        "elitism_count": {
            "title": "Elitism Count", "type": "integer", "default": 2,
            "minimum": 0, "maximum": 20,
        },
        "use_hybrid_init": {
            "title": "Hybrid Init", "type": "boolean", "default": True,
        },
        "use_tiered_operators": {
            "title": "Tiered Operators", "type": "boolean", "default": True,
        },
        "use_kb": {
            "title": "Use Knowledge Base", "type": "boolean", "default": True,
        },
        "fdr_alpha": {
            "title": "FDR Alpha", "type": "number", "default": 0.05,
            "minimum": 0.01, "maximum": 0.2,
        },
        "max_workers": {
            "title": "Max Workers", "type": "integer", "default": 4,
            "minimum": 1, "maximum": 16,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        codes = inputs.get("codes", [])
        if isinstance(codes, pd.DataFrame):
            codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)
        if not codes:
            return {
                "best_factors": {"error": "No stock codes provided"},
                "generation_log": [],
            }

        try:
            from src.factors.mining.gp_engine import GPEvolution, GPEvolutionConfig
        except ImportError as e:
            logger.exception("GP import failed")
            return {
                "best_factors": {"error": f"GP engine not available: {e}"},
                "generation_log": [],
            }

        # ── Build config ──────────────────────────────────────────────────────
        gp_config = GPEvolutionConfig(
            population_size=int(config.get("population_size", 100)),
            generations=int(config.get("generations", 50)),
            tournament_size=int(config.get("tournament_size", 7)),
            crossover_prob=float(config.get("crossover_prob", 0.7)),
            mutation_prob=float(config.get("mutation_prob", 0.2)),
            elitism_count=int(config.get("elitism_count", 2)),
            train_start=config.get("train_start", "2024-01-01"),
            train_end=config.get("train_end", "2025-12-31"),
            test_start=config.get("test_start", "2025-01-01"),
            test_end=config.get("test_end", "2025-12-31"),
            universe=list(codes),
            max_workers=int(config.get("max_workers", 4)),
            use_tiered_operators=config.get("use_tiered_operators", True),
            use_hybrid_init=config.get("use_hybrid_init", True),
            use_kb=config.get("use_kb", True),
            fdr_alpha=float(config.get("fdr_alpha", 0.05)),
        )

        # ── Run GP evolution ──────────────────────────────────────────────────
        logger.info("GPEvolution: pop=%d gen=%d codes=%d", gp_config.population_size, gp_config.generations, len(codes))
        try:
            gp = GPEvolution(config=gp_config)
            result = gp.run()

            # ── Collect best factors ──────────────────────────────────────────
            best_factors: List[Dict[str, Any]] = []
            for ind in result.best_individuals[:10]:
                best_factors.append({
                    "formula": ind.tree.to_formula(),
                    "formula_hash": ind.tree.formula_hash,
                    "fitness": round(float(ind.fitness), 4),
                    "ic_train": round(float(ind.ic_train), 4) if hasattr(ind, "ic_train") else None,
                    "ic_test": round(float(ind.ic_test), 4) if hasattr(ind, "ic_test") else None,
                    "generation": ind.generation,
                })

            # ── Generation log ────────────────────────────────────────────────
            gen_log: List[Dict[str, Any]] = []
            for gen_idx, gen_data in enumerate(result.generation_history):
                gen_log.append({
                    "generation": gen_idx,
                    "best_fitness": round(float(gen_data.best_fitness), 4),
                    "mean_fitness": round(float(gen_data.mean_fitness), 4),
                    "median_fitness": round(float(gen_data.median_fitness), 4) if gen_data.median_fitness is not None else None,
                    "unique_count": gen_data.unique_count,
                })

            logger.info("GPEvolution: done — %d best factors, best fitness=%.4f", len(best_factors), best_factors[0]["fitness"] if best_factors else 0)

            return {
                "best_factors": {
                    "factors": best_factors,
                    "n_total_evaluated": len(best_factors),
                    "config": gp_config.model_dump() if hasattr(gp_config, "model_dump") else {},
                },
                "generation_log": gen_log,
            }

        except Exception as e:
            logger.exception("GPEvolution failed")
            return {
                "best_factors": {"error": str(e)},
                "generation_log": [],
            }
