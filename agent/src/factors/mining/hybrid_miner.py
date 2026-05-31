"""Hybrid GP + LLM co-evolution for factor mining.

LLM reviews GP population state and suggests search directions.
GP executes with bias toward LLM-suggested patterns.
LLM filters GP-discovered candidates for financial logic.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from src.factors.mining.gp_engine import (
    GPEvolution,
    GPEvolutionConfig,
    GPIndividual,
    GPRunResult,
)
from src.factors.mining.llm_miner import FactorCandidate, LLMFactorMiner

logger = logging.getLogger(__name__)


class HybridConfig(BaseModel):
    """Configuration for hybrid mining."""

    max_cycles: int = Field(default=5, ge=1, le=20)
    gp_config: GPEvolutionConfig = Field(default_factory=GPEvolutionConfig)
    llm_review_batch_size: int = Field(default=10, description="Top N GP individuals for LLM review")
    llm_suggestion_enabled: bool = Field(default=True)
    llm_filter_enabled: bool = Field(default=True)


class HybridResult(BaseModel):
    """Result of a hybrid mining run."""

    job_id: str
    cycles_completed: int
    gp_results: list[dict[str, Any]] = Field(default_factory=list)
    llm_accepted: list[dict[str, Any]] = Field(default_factory=list)
    llm_rejected: list[dict[str, Any]] = Field(default_factory=list)
    best_factors: list[dict[str, Any]] = Field(default_factory=list)
    runtime_seconds: float = 0.0


REVIEW_PROMPT = """You are a quantitative finance researcher reviewing alpha factor formulas
discovered by genetic programming. For each formula, judge whether it makes
financial/economic sense.

Formulas to review:
{formulas}

For each formula, respond:
- pass: true if the formula has a reasonable economic interpretation
- reason: one-line explanation of what the formula measures (or why it doesn't make sense)
- score: 0-100 for how robust this factor is likely to be out-of-sample

Output as JSON array:
[{{"index": 0, "pass": true, "reason": "...", "score": 75}}]

Only output valid JSON, no commentary."""


class HybridMiner:
    """Orchestrates GP + LLM co-evolution for factor discovery."""

    def __init__(self, config: HybridConfig | None = None) -> None:
        self.config = config or HybridConfig()
        self._llm_miner = LLMFactorMiner()

    def run(self) -> HybridResult:
        """Execute hybrid mining cycles.

        Each cycle:
        1. Run GP evolution (small, focused runs)
        2. LLM reviews top individuals (rate-limited: every Nth cycle)
        3. Filter and accumulate best factors

        Cost control: LLM review is only called every 5 cycles by default.
        Returns:
            HybridResult with accepted/rejected factors.
        """
        import time
        import uuid

        job_id = uuid.uuid4().hex[:12]
        start_time = time.monotonic()
        llm_review_interval = max(1, self.config.gp_config.generations // 10)  # ~every 5 gens

        result = HybridResult(job_id=job_id)

        for cycle in range(self.config.max_cycles):
            logger.info("Hybrid cycle %d/%d", cycle + 1, self.config.max_cycles)

            # Run focused GP
            gp = GPEvolution(config=self.config.gp_config)
            gp_result = gp.run()

            result.gp_results.append({
                "cycle": cycle + 1,
                "best_ic": gp_result.best_test_ic,
                "best_formula": gp_result.best_individuals[0].formula if gp_result.best_individuals else "",
                "generations": len(gp_result.generation_history),
            })

            # LLM review — rate-limited to control cost
            if (
                self.config.llm_filter_enabled
                and gp_result.best_individuals
                and (cycle == 0 or cycle % llm_review_interval == 0 or cycle == self.config.max_cycles - 1)
            ):
                try:
                    top_n = gp_result.best_individuals[:self.config.llm_review_batch_size]
                    formulas_text = "\n\n".join(
                        f"Formula {i}: {ind.formula}  (IC={ind.test_ic:.4f}, IR={ind.test_ir:.2f})"
                        for i, ind in enumerate(top_n)
                    )

                    from src.factors.mining.llm_miner import _JSON_SCHEMA_REVIEW
                    review_response = self._llm_miner._call_llm(
                        REVIEW_PROMPT.format(formulas=formulas_text),
                        json_schema=_JSON_SCHEMA_REVIEW,
                    )

                    if review_response:
                        reviews = self._llm_miner._parse_json_response(review_response)
                        for rev in reviews:
                            idx = rev.get("index", -1)
                            if 0 <= idx < len(top_n):
                                entry = {
                                    "formula": top_n[idx].formula,
                                    "train_fitness": top_n[idx].train_fitness,
                                    "test_ic": top_n[idx].test_ic,
                                    "test_ir": top_n[idx].test_ir,
                                    "llm_score": rev.get("score", 0),
                                    "llm_reason": rev.get("reason", ""),
                                }
                                if rev.get("pass", False):
                                    result.llm_accepted.append(entry)
                                else:
                                    result.llm_rejected.append(entry)
                except RuntimeError as e:
                    # Rate limit or budget exceeded — skip LLM review this cycle
                    logger.warning("LLM review skipped (cycle %d): %s", cycle + 1, e)

        # Compile best factors from accepted
        accepted_sorted = sorted(result.llm_accepted, key=lambda x: x.get("llm_score", 0), reverse=True)
        result.best_factors = accepted_sorted[:10]
        result.runtime_seconds = round(time.monotonic() - start_time, 1)
        result.cycles_completed = self.config.max_cycles

        return result
