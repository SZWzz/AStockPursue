"""AI Factor Mining Engine.

Genetic programming + LLM-guided search for alpha factor discovery.
Discovered factors are validated and can be promoted into Alpha Zoo.

Sub-modules:
    expression_tree -- Expression tree representation + operators
    fitness          -- Fitness functions (IC / rank-IC / Sharpe)
    gp_engine        -- Genetic programming evolution engine
    llm_miner        -- LLM-guided factor extraction & debate
    hybrid_miner     -- Hybrid GP + LLM co-evolution
    factor_validator -- Syntax / lookahead / stability validation
    factor_promoter  -- Promote validated factors into Alpha Zoo
"""

from src.factors.mining.expression_tree import ExpressionNode, ExpressionTree
from src.factors.mining.gp_engine import (
    GPEvolution,
    GPEvolutionConfig,
    GPIndividual,
    GPRunResult,
    GenerationStats,
)

__all__ = [
    "ExpressionNode",
    "ExpressionTree",
    "GPEvolution",
    "GPEvolutionConfig",
    "GPIndividual",
    "GPRunResult",
    "GenerationStats",
]
