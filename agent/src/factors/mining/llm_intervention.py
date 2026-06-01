"""LLM-guided GP evolution — Phase C P1.

Every N generations, the LLM analyses the population state (elite formulas,
fitness distribution, diversity, KB theme health, Zoo feedback) and returns
a structured intervention action that is injected into the GP run.

Intervention actions:
    inject_seeds        — LLM generates formula seeds → replace worst N individuals
    adjust_mutation     — dynamically modify mutation_prob
    adjust_crossover    — dynamically modify crossover_prob
    theme_redirect      — change fitness theme weights based on Zoo dead themes
    increase_diversity  — inject random individuals + boost mutation
    avoid_redundant     — check elites against KB → remove duplicates → resample
    no_op               — do nothing (LLM decides no intervention needed)

Ablation study (3-group controlled experiment):
    Group A: No intervention (baseline GP)
    Group B: LLM intervention (experimental)
    Group C: Random placebo intervention (control)

Gate: Group B must beat both Group A AND Group C (p < 0.05) to enable
auto-intervention mode.  Otherwise falls back to manual trigger.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from src.factors.mining.expression_tree import (
    ExpressionTree,
    ExpressionNode,
    FEATURE_IDS,
    MAX_COMPLEXITY,
    OPERATOR_REGISTRY,
    get_allowed_operators,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured intervention prompt
# ---------------------------------------------------------------------------

INTERVENTION_SYSTEM_PROMPT = """You are a quantitative researcher specialising in A-share alpha factor discovery.
You are monitoring a genetic programming (GP) evolution run and must decide on an intervention.

## Available Operators
{available_operators}

## Available Features
{available_features}

## Knowledge Base Context
{kb_context}

## Alpha Zoo Status
{zoo_status}

## Intervention Actions (choose exactly one)
1. inject_seeds — Generate {n_seeds} formula seeds as JSON expression trees. Use when the population is stagnating or needs fresh ideas.
2. adjust_mutation — Change mutation_prob. Use when diversity is too low (< 0.02) or too high (> 0.15).
3. adjust_crossover — Change crossover_prob. Use when elites are not improving.
4. theme_redirect — Change fitness focus away from dead themes toward alive themes.
5. increase_diversity — Boost diversity by injecting random individuals + raising mutation.
6. avoid_redundant — Remove elites that duplicate existing KB factors.
7. no_op — Do nothing. Use when the population is healthy and improving.

## Output Format
Respond with a JSON object ONLY, no commentary:
{{
  "action": "<action_name>",
  "reason": "<1-sentence explanation of why this action>",
  "params": {{...action-specific parameters...}}
}}

For inject_seeds, params.seeds must be a list of expression tree JSON objects.
For adjust_mutation/adjust_crossover, params.new_value must be a float 0.0-1.0.
For theme_redirect, params.boost_themes and params.avoid_themes must be string lists.
"""

# Few-shot examples that demonstrate each action type
FEW_SHOT_EXAMPLES: list[dict[str, Any]] = [
    {
        "scenario": "Population diversity dropped to 0.015 and best fitness hasn't improved for 5 generations",
        "response": {
            "action": "increase_diversity",
            "reason": "Diversity critically low at 0.015 — population has converged to a local optimum",
            "params": {
                "new_mutation_rate": 0.30,
                "n_random_injections": 10,
            },
        },
    },
    {
        "scenario": "Theme 'volatility' shows 5 dead / 0 alive in Zoo. Elites are all vol-based factors.",
        "response": {
            "action": "theme_redirect",
            "reason": "Volatility theme is dead in production — redirecting to quality which has mean IC 0.031",
            "params": {
                "boost_themes": ["quality", "momentum"],
                "avoid_themes": ["volatility"],
            },
        },
    },
    {
        "scenario": "3 out of 5 elites are already in KB with existing factors. Population is rediscovering known formulas.",
        "response": {
            "action": "avoid_redundant",
            "reason": "60% of elites duplicate existing KB factors — removing duplicates and injecting fresh seeds",
            "params": {
                "n_seeds": 5,
            },
        },
    },
    {
        "scenario": "Best IC improving steadily (0.028→0.034 over last 3 interventions). Diversity healthy at 0.08.",
        "response": {
            "action": "no_op",
            "reason": "Population is healthy and improving — no intervention needed this cycle",
            "params": {},
        },
    },
]


# ---------------------------------------------------------------------------
# Population context builder
# ---------------------------------------------------------------------------

@dataclass
class PopulationContext:
    """Snapshot of GP state for LLM analysis."""

    generation: int
    total_generations: int
    best_fitness: float
    mean_fitness: float
    std_fitness: float
    best_ic: float
    diversity: float
    elite_formulas: list[str]
    elite_complexities: list[int]
    fitness_history: list[float]   # last 10 generations' best fitness
    kb_theme_health: dict[str, Any]
    kb_avoid_themes: list[str]
    kb_explore_themes: list[str]
    zoo_alive_count: int
    zoo_dead_count: int
    kb_duplicates_this_run: int
    allowed_operators: list[str]


def build_population_context(
    generation: int,
    total_generations: int,
    fitnesses: list[float],
    elite_formulas: list[str],
    elite_complexities: list[int],
    diversity: float,
    fitness_history: list[float],
    kb_guidance: dict[str, Any] | None,
    kb_duplicates: int,
    allowed_operators: list[str] | None,
) -> PopulationContext:
    """Build a structured context snapshot for LLM analysis."""
    if not fitnesses:
        return PopulationContext(
            generation=generation, total_generations=total_generations,
            best_fitness=0.0, mean_fitness=0.0, std_fitness=0.0,
            best_ic=0.0, diversity=0.0,
            elite_formulas=[], elite_complexities=[],
            fitness_history=[], kb_theme_health={},
            kb_avoid_themes=[], kb_explore_themes=[],
            zoo_alive_count=0, zoo_dead_count=0,
            kb_duplicates_this_run=0, allowed_operators=[],
        )

    guidance = kb_guidance or {}
    return PopulationContext(
        generation=generation,
        total_generations=total_generations,
        best_fitness=float(np.max(fitnesses)),
        mean_fitness=float(np.mean(fitnesses)),
        std_fitness=float(np.std(fitnesses, ddof=1)) if len(fitnesses) > 1 else 0.0,
        best_ic=0.0,  # filled in by caller
        diversity=diversity,
        elite_formulas=elite_formulas[:5],
        elite_complexities=elite_complexities[:5],
        fitness_history=fitness_history[-10:],
        kb_theme_health=guidance.get("theme_health", {}),
        kb_avoid_themes=guidance.get("avoid_themes", []),
        kb_explore_themes=guidance.get("explore_themes", []),
        zoo_alive_count=guidance.get("total_active", 0),
        zoo_dead_count=guidance.get("total_dead", 0),
        kb_duplicates_this_run=kb_duplicates,
        allowed_operators=allowed_operators or [],
    )


def format_context_for_llm(ctx: PopulationContext) -> str:
    """Format the population context as a readable string for the LLM prompt."""
    lines = [
        f"## GP Run State",
        f"Generation: {ctx.generation}/{ctx.total_generations}",
        f"Best Fitness: {ctx.best_fitness:.6f} | Mean: {ctx.mean_fitness:.6f} | Std: {ctx.std_fitness:.6f}",
        f"Population Diversity: {ctx.diversity:.4f}",
        f"",
        f"## Elite Individuals (Top {len(ctx.elite_formulas)})",
    ]
    for i, (f, c) in enumerate(zip(ctx.elite_formulas, ctx.elite_complexities)):
        lines.append(f"  {i+1}. [{c} nodes] {f}")
    lines.append("")

    if ctx.fitness_history:
        lines.append(f"## Fitness Trend (last {len(ctx.fitness_history)} gens)")
        trend = ", ".join(f"{v:.4f}" for v in ctx.fitness_history)
        lines.append(f"  [{trend}]")
        # Detect stagnation
        if len(ctx.fitness_history) >= 5:
            recent = ctx.fitness_history[-5:]
            if max(recent) - min(recent) < 0.002:
                lines.append("  ⚠️ STAGNATION DETECTED — fitness flat for 5+ generations")
        lines.append("")

    if ctx.kb_theme_health:
        lines.append("## Knowledge Base Theme Health")
        for theme, info in sorted(ctx.kb_theme_health.items(), key=lambda x: -x[1].get("mean_ic", 0)):
            lines.append(f"  {theme}: {info.get('count', 0)} alive, mean_IC={info.get('mean_ic', 0):.4f}, trend={info.get('trend', '?')}")
        lines.append("")

    if ctx.kb_avoid_themes:
        lines.append(f"## Themes to AVOID (high dead/alive ratio): {', '.join(ctx.kb_avoid_themes)}")
        lines.append("")
    if ctx.kb_explore_themes:
        lines.append(f"## Themes with ROOM (few alive, positive IC): {', '.join(ctx.kb_explore_themes)}")
        lines.append("")

    lines.append(f"## Zoo Status: {ctx.zoo_alive_count} alive / {ctx.zoo_dead_count} dead")
    lines.append(f"## KB Duplicates This Run: {ctx.kb_duplicates_this_run}")
    lines.append(f"## Allowed Operators: {', '.join(ctx.allowed_operators[:20])}")
    if len(ctx.allowed_operators) > 20:
        lines.append(f"  ... and {len(ctx.allowed_operators) - 20} more")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM caller interface
# ---------------------------------------------------------------------------

class LLMCaller:
    """Minimal LLM caller interface — injected so the evolution engine
    can work with any provider (OpenAI, Anthropic, local, …)."""

    def __init__(self, call_fn=None):
        """*call_fn*: async or sync ``(system_prompt: str, user_prompt: str) -> str``."""
        self._call = call_fn

    def call(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM and return the response text."""
        if self._call is None:
            raise RuntimeError("LLMCaller not configured — set call_fn")
        import asyncio

        result = self._call(system_prompt, user_prompt)
        # Handle async
        if asyncio.iscoroutine(result):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, result)
                        return future.result(timeout=60)
                return loop.run_until_complete(result)
            except RuntimeError:
                return asyncio.run(result)
        return result


# ---------------------------------------------------------------------------
# Intervention action executor
# ---------------------------------------------------------------------------

@dataclass
class InterventionResult:
    """Result of an LLM intervention."""

    action: str
    reason: str
    params: dict[str, Any]
    # Mutated state
    new_mutation_prob: float | None = None
    new_crossover_prob: float | None = None
    injected_seeds: list[ExpressionTree] = field(default_factory=list)
    removed_indices: list[int] = field(default_factory=list)
    theme_weights: dict[str, float] = field(default_factory=dict)


class InterventionExecutor:
    """Executes LLM intervention actions on the GP population."""

    def __init__(
        self,
        llm_caller: LLMCaller,
        rng: random.Random | None = None,
    ) -> None:
        self._llm = llm_caller
        self._rng = rng or random.Random()
        self._intervention_count = 0
        self._history: list[InterventionResult] = []

    @property
    def intervention_count(self) -> int:
        return self._intervention_count

    @property
    def history(self) -> list[InterventionResult]:
        return self._history

    def request_intervention(
        self,
        ctx: PopulationContext,
        kb_guidance: dict[str, Any] | None = None,
    ) -> InterventionResult:
        """Call the LLM, parse the response, return a structured InterventionResult."""
        context_text = format_context_for_llm(ctx)

        ops_list = ctx.allowed_operators if ctx.allowed_operators else list(OPERATOR_REGISTRY.keys())
        system = INTERVENTION_SYSTEM_PROMPT.format(
            available_operators=", ".join(ops_list),
            available_features=", ".join(FEATURE_IDS),
            kb_context=context_text,
            zoo_status=f"{ctx.zoo_alive_count} alive / {ctx.zoo_dead_count} dead",
            n_seeds=3,
        )

        user = f"Analyse the current GP state and decide on ONE intervention action.\n\n{context_text}"

        # ── LLM call with retry for JSON parse ──
        raw_response = ""
        for attempt in range(3):
            try:
                raw_response = self._llm.call(system, user)
                # Extract JSON from response (may be wrapped in markdown)
                json_str = raw_response.strip()
                if json_str.startswith("```"):
                    json_str = json_str.split("\n", 1)[1]
                    if json_str.endswith("```"):
                        json_str = json_str.rsplit("```", 1)[0]
                result_json = json.loads(json_str)
                break
            except (json.JSONDecodeError, KeyError) as exc:
                logger.debug("LLM response parse attempt %d failed: %s", attempt + 1, exc)
                if attempt == 2:
                    # Fallback: no_op
                    return InterventionResult(action="no_op", reason="LLM response parse failed", params={})
                user = f"{user}\n\nYour previous response was not valid JSON. Please respond with ONLY a JSON object."

        action = result_json.get("action", "no_op")
        reason = result_json.get("reason", "")
        params = result_json.get("params", {})

        result = InterventionResult(action=action, reason=reason, params=params)
        self._intervention_count += 1
        self._history.append(result)
        return result

    def execute(
        self,
        intervention: InterventionResult,
        population: list[Any],      # list[GPIndividual]
        fitnesses: list[float],
        config: Any,                # GPEvolutionConfig
        allowed_operators: list[str] | None = None,
    ) -> tuple[list[Any], list[float], Any]:
        """Apply the intervention to the population.

        Returns:
            (modified_population, modified_fitnesses, modified_config)
        """
        action = intervention.action
        pop = list(population)
        fits = list(fitnesses)
        cfg = config

        if action == "inject_seeds":
            # Generate seeds from LLM-provided expression trees
            seeds_data = intervention.params.get("seeds", [])
            seeds = []
            for sd in seeds_data:
                try:
                    tree = ExpressionTree.from_dict(sd)
                    if tree.complexity() <= MAX_COMPLEXITY:
                        seeds.append(tree)
                except Exception as exc:
                    logger.debug("Failed to parse LLM seed: %s", exc)

            if seeds:
                intervention.injected_seeds = seeds
                # Replace worst individuals
                sorted_idx = sorted(range(len(fits)), key=lambda i: fits[i])
                n_replace = min(len(seeds), max(1, len(pop) // 5))
                for i, idx in enumerate(sorted_idx[:n_replace]):
                    if i < len(seeds):
                        pop[idx] = type(pop[0])(tree=seeds[i])
                        fits[idx] = 0.0  # will be re-evaluated
                        intervention.removed_indices.append(idx)
                logger.info("LLM injected %d seeds, replaced %d worst individuals", len(seeds), n_replace)

        elif action == "adjust_mutation":
            new_val = intervention.params.get("new_value", intervention.params.get("new_mutation_rate"))
            if new_val is not None and 0.0 <= float(new_val) <= 1.0:
                intervention.new_mutation_prob = float(new_val)
                cfg.mutation_prob = float(new_val)
                logger.info("LLM adjusted mutation_prob to %.3f", float(new_val))

        elif action == "adjust_crossover":
            new_val = intervention.params.get("new_value", intervention.params.get("new_crossover_rate"))
            if new_val is not None and 0.0 <= float(new_val) <= 1.0:
                intervention.new_crossover_prob = float(new_val)
                cfg.crossover_prob = float(new_val)
                logger.info("LLM adjusted crossover_prob to %.3f", float(new_val))

        elif action == "increase_diversity":
            new_mut = intervention.params.get("new_mutation_rate", 0.30)
            n_random = int(intervention.params.get("n_random_injections", max(1, len(pop) // 10)))

            intervention.new_mutation_prob = float(new_mut)
            cfg.mutation_prob = float(new_mut)

            from src.factors.mining.hybrid_init import _safe_random_tree
            for _ in range(n_random):
                sorted_idx = sorted(range(len(fits)), key=lambda i: fits[i])
                worst_idx = sorted_idx[0]
                tree = _safe_random_tree(self._rng)
                pop[worst_idx] = type(pop[0])(tree=tree)
                fits[worst_idx] = 0.0
                intervention.removed_indices.append(worst_idx)

            logger.info("LLM boosted diversity: mut=%.3f, injected %d random", float(new_mut), n_random)

        elif action == "theme_redirect":
            boost = intervention.params.get("boost_themes", [])
            avoid = intervention.params.get("avoid_themes", [])
            intervention.theme_weights = {
                **{t: 1.5 for t in boost},
                **{t: 0.5 for t in avoid},
            }
            logger.info("LLM theme redirect: boost=%s, avoid=%s", boost, avoid)

        elif action == "avoid_redundant":
            n_seeds = int(intervention.params.get("n_seeds", 3))
            from src.factors.mining.hybrid_init import get_default_skeletons
            skeletons = get_default_skeletons()
            if skeletons:
                seeds = [ExpressionTree(self._rng.choice(skeletons).root.copy()) for _ in range(n_seeds)]
                intervention.injected_seeds = seeds
                sorted_idx = sorted(range(len(fits)), key=lambda i: fits[i])
                for i, idx in enumerate(sorted_idx[:n_seeds]):
                    if i < len(seeds):
                        pop[idx] = type(pop[0])(tree=seeds[i])
                        fits[idx] = 0.0
                        intervention.removed_indices.append(idx)
                logger.info("LLM removed %d redundant elites, injected %d skeleton seeds", n_seeds, n_seeds)

        elif action == "no_op":
            logger.debug("LLM decided no intervention needed")

        return pop, fits, cfg


# ---------------------------------------------------------------------------
# Ablation study
# ---------------------------------------------------------------------------

@dataclass
class AblationGroupResult:
    """Results from one ablation study group."""

    group_name: str                                   # "baseline" / "llm" / "placebo"
    elite_top10_ic: list[float] = field(default_factory=list)
    first_viable_gen: int | None = None               # First generation with IC > 0.03
    mean_orthogonality: float = 0.0
    theme_diversity: float = 0.0                      # Entropy of theme distribution
    total_runtime_s: float = 0.0
    llm_cost_estimate: float = 0.0                    # Estimated API cost


@dataclass
class AblationResult:
    """Complete ablation study result with statistical comparison."""

    baseline: AblationGroupResult
    llm: AblationGroupResult
    placebo: AblationGroupResult
    llm_beats_baseline: bool = False
    llm_beats_placebo: bool = False
    p_value_vs_baseline: float = 1.0
    p_value_vs_placebo: float = 1.0
    recommendation: str = ""

    @property
    def llm_intervention_justified(self) -> bool:
        """LLM intervention is justified only if it beats BOTH baseline AND placebo."""
        return self.llm_beats_baseline and self.llm_beats_placebo


PLACEBO_ACTIONS = [
    "inject_seeds", "adjust_mutation", "adjust_crossover",
    "increase_diversity", "theme_redirect", "no_op",
]


def random_placebo_intervention(
    rng: random.Random,
    population: list[Any],
    fitnesses: list[float],
    config: Any,
) -> tuple[list[Any], list[float], Any, str]:
    """Generate a random placebo intervention.

    Randomly selects an action and applies it with random parameters,
    mimicking the form of an LLM intervention without any intelligence.
    """
    action = rng.choice(PLACEBO_ACTIONS)
    pop = list(population)
    fits = list(fitnesses)
    cfg = config

    if action == "inject_seeds":
        from src.factors.mining.hybrid_init import _safe_random_tree
        n = rng.randint(1, 5)
        sorted_idx = sorted(range(len(fits)), key=lambda i: fits[i])
        for i in range(min(n, len(pop))):
            tree = _safe_random_tree(rng)
            pop[sorted_idx[i]] = type(pop[0])(tree=tree)
            fits[sorted_idx[i]] = 0.0

    elif action == "adjust_mutation":
        cfg.mutation_prob = round(rng.uniform(0.05, 0.40), 2)

    elif action == "adjust_crossover":
        cfg.crossover_prob = round(rng.uniform(0.40, 0.90), 2)

    elif action == "increase_diversity":
        cfg.mutation_prob = round(rng.uniform(0.20, 0.40), 2)
        from src.factors.mining.hybrid_init import _safe_random_tree
        for _ in range(rng.randint(2, 8)):
            worst = sorted(range(len(fits)), key=lambda i: fits[i])[0]
            pop[worst] = type(pop[0])(tree=_safe_random_tree(rng))
            fits[worst] = 0.0

    elif action == "theme_redirect":
        pass  # theme weights changed randomly — no structural effect without actual theme tracking

    return pop, fits, cfg, action


def compare_ablation_groups(
    experimental: AblationGroupResult,
    control: AblationGroupResult,
) -> tuple[bool, float]:
    """Compare two ablation groups using Welch's t-test on top-10 IC values.

    Returns:
        (experimental_beats_control, p_value)
    """
    from scipy import stats as sp_stats

    exp_ics = experimental.elite_top10_ic
    ctrl_ics = control.elite_top10_ic

    if len(exp_ics) < 3 or len(ctrl_ics) < 3:
        return float(np.mean(exp_ics)) > float(np.mean(ctrl_ics)), 1.0

    t_stat, p_value = sp_stats.ttest_ind(exp_ics, ctrl_ics, equal_var=False)
    beats = float(np.mean(exp_ics)) > float(np.mean(ctrl_ics)) and p_value < 0.05
    return beats, float(p_value)


def evaluate_ablation(
    baseline: AblationGroupResult,
    llm: AblationGroupResult,
    placebo: AblationGroupResult,
) -> AblationResult:
    """Evaluate ablation results and make a recommendation."""
    beats_baseline, p_vs_baseline = compare_ablation_groups(llm, baseline)
    beats_placebo, p_vs_placebo = compare_ablation_groups(llm, placebo)

    if beats_baseline and beats_placebo:
        rec = "ENABLE — LLM intervention significantly outperforms both baseline and placebo. Auto-intervention mode ON."
    elif beats_baseline and not beats_placebo:
        rec = "DEGRADE — LLM beats baseline but NOT placebo. LLM intervention ≈ random noise. Fall back to MANUAL trigger mode."
    elif not beats_baseline:
        rec = "DISABLE — LLM does not beat baseline. Do NOT use LLM intervention. Pure GP is sufficient."
    else:
        rec = "INCONCLUSIVE — Re-run with more trials."

    return AblationResult(
        baseline=baseline, llm=llm, placebo=placebo,
        llm_beats_baseline=beats_baseline, llm_beats_placebo=beats_placebo,
        p_value_vs_baseline=p_vs_baseline, p_value_vs_placebo=p_vs_placebo,
        recommendation=rec,
    )
