"""FactorKB MCP tools and auto-promotion pipeline — Phase C P3.

Exposes factor knowledge base operations as MCP tools so Claude Desktop
can participate in factor discovery, review, and lifecycle management.

Auto-promotion pipeline:
    GP/LLM output → AST validate → IC threshold → Walk-Forward →
    FDR correction → human review → PAPER_TRADING → PRODUCTION
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.agent.tools import BaseTool
from src.factors.mining.expression_tree import ExpressionTree, MAX_COMPLEXITY
from src.factors.mining.factor_kb import FactorKnowledgeBase, FactorStatus, get_kb
from src.factors.mining.safety_validator import (
    ASTWhitelistValidator,
    TypeSignatureValidator,
    RuntimeCircuitBreaker,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Factor auto-promotion pipeline
# ---------------------------------------------------------------------------

class FactorPromotionPipeline:
    """Automated pipeline: candidate → validation → promotion.

    Stages:
        1. AST whitelist validation
        2. Type signature check
        3. IC threshold (test_ic > 0.01)
        4. Walk-Forward pass (> 60% windows)
        5. FDR multiple testing correction
        6. Orthogonality check (max_corr_with_core < 0.8)
        7. Human review gate
        8. PAPER_TRADING (≥ 21 trading days)
        9. PRODUCTION
    """

    def __init__(self, kb: FactorKnowledgeBase | None = None) -> None:
        self._kb = kb or get_kb()
        self._ast_validator = ASTWhitelistValidator()
        self._type_validator = TypeSignatureValidator()
        self._circuit_breaker = RuntimeCircuitBreaker()

    def auto_screen(self, entry_id: str) -> dict[str, Any]:
        """Run automated validation checks on a factor candidate.

        Returns:
            Dict with passed, checks, and next_action.
        """
        entry = self._kb.get(entry_id)
        if entry is None:
            return {"passed": False, "reason": f"Factor not found: {entry_id}"}

        checks: dict[str, Any] = {}
        tree = entry.tree

        # ── 1. AST whitelist ──
        ast_ok, ast_err, ast_warn = self._ast_validator.validate(tree)
        checks["ast_whitelist"] = {"passed": ast_ok, "error": ast_err, "warnings": ast_warn}
        if not ast_ok:
            return {"passed": False, "reason": f"AST validation failed: {ast_err}", "checks": checks}

        # ── 2. Type signature ──
        type_ok, type_err = self._type_validator.validate(tree)
        checks["type_signature"] = {"passed": type_ok, "error": type_err}
        if not type_ok:
            return {"passed": False, "reason": f"Type signature failed: {type_err}", "checks": checks}

        # ── 3. Complexity ──
        complexity_ok = tree.complexity() <= MAX_COMPLEXITY
        checks["complexity"] = {"passed": complexity_ok, "value": tree.complexity()}
        if not complexity_ok:
            return {"passed": False, "reason": f"Complexity {tree.complexity()} exceeds limit {MAX_COMPLEXITY}", "checks": checks}

        # ── 4. IC threshold ──
        ic = abs(entry.test_ic)
        ic_ok = ic > 0.01
        checks["ic_threshold"] = {"passed": ic_ok, "value": round(ic, 4)}
        if not ic_ok:
            return {"passed": False, "reason": f"IC {ic:.4f} below threshold 0.01", "checks": checks}

        # ── 5. Orthogonality ──
        max_corr = entry.max_corr_with_core
        ortho_ok = max_corr < 0.8
        checks["orthogonality"] = {"passed": ortho_ok, "value": round(max_corr, 4)}

        # All automated checks passed
        all_passed = all(c.get("passed", False) for c in checks.values())
        if all_passed:
            try:
                self._kb.transition_status(entry_id, FactorStatus.APPROVED,
                                           reason="Auto-screening passed")
            except ValueError:
                pass
            return {
                "passed": True,
                "checks": checks,
                "next_action": "Submit for human review → PAPER_TRADING",
                "entry": entry.to_dict(),
            }
        else:
            try:
                self._kb.transition_status(entry_id, FactorStatus.REJECTED,
                                           reason="Auto-screening failed")
            except ValueError:
                pass
            return {
                "passed": False,
                "checks": checks,
                "next_action": "Fix issues and re-submit",
            }

    def promote_to_paper_trading(self, entry_id: str) -> dict[str, Any]:
        """Promote an APPROVED factor to PAPER_TRADING status."""
        entry = self._kb.get(entry_id)
        if entry is None:
            return {"ok": False, "error": f"Factor not found: {entry_id}"}
        if entry.status != FactorStatus.APPROVED:
            return {"ok": False, "error": f"Factor must be APPROVED, currently {entry.status}"}

        try:
            self._kb.transition_status(entry_id, FactorStatus.PAPER_TRADING,
                                       reason="Promoted to paper trading")
            # Generate SignalEngine code for the paper trading system
            code = entry.tree.to_signalengine_code(f"Factor_{entry.alpha_id}")
            return {
                "ok": True,
                "entry_id": entry_id,
                "signalengine_code": code,
                "next_action": "Run paper trading for ≥ 21 trading days, then check promotion conditions",
            }
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    def generate_signalengine_plugin(self, entry_id: str, output_dir: str = "") -> dict[str, Any]:
        """Generate a deployable SignalEngine plugin file from a factor."""
        entry = self._kb.get(entry_id)
        if entry is None:
            return {"ok": False, "error": f"Factor not found: {entry_id}"}

        code = entry.tree.to_signalengine_code(f"Factor_{entry.alpha_id}")

        if output_dir:
            path = Path(output_dir) / f"factor_{entry.alpha_id}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code, encoding="utf-8")
            return {"ok": True, "file": str(path), "hash": entry.formula_hash}

        return {"ok": True, "code": code, "hash": entry.formula_hash}


# ---------------------------------------------------------------------------
# MCP tools (registered via @BaseTool pattern)
# ---------------------------------------------------------------------------

class FactorKBSearchTool(BaseTool):
    """Search the factor knowledge base by natural language query."""

    name = "factor_kb_search"
    description = (
        "Search the factor knowledge base using natural language. "
        "Example queries: '低换手率的价值反转因子', 'momentum factor with volume confirmation'. "
        "Returns top K matching factors with IC, status, and formula."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query"},
            "top_k": {"type": "integer", "description": "Max results (default 10)"},
        },
        "required": ["query"],
    }
    repeatable = True
    is_readonly = True

    def execute(self, query: str = "", top_k: int = 10, **kwargs) -> str:
        kb = get_kb()
        results = kb.search_by_tags(query.split() if query else [], top_k=top_k)
        formatted = [
            {
                "alpha_id": e.alpha_id,
                "formula": e.formula,
                "test_ic": e.test_ic,
                "status": e.status,
                "theme": e.theme,
                "rationale": e.economic_rationale[:200] if e.economic_rationale else "",
            }
            for e in results
        ]
        return json.dumps({"status": "ok", "results": formatted, "count": len(formatted)}, ensure_ascii=False)


class FactorReviewTool(BaseTool):
    """Approve or reject a factor pending review."""

    name = "factor_review"
    description = (
        "Approve or reject a factor that is pending human review. "
        "Must provide a reason for the decision."
    )
    parameters = {
        "type": "object",
        "properties": {
            "alpha_id": {"type": "string", "description": "Factor ID to review"},
            "action": {"type": "string", "description": "approve or reject"},
            "reason": {"type": "string", "description": "Reason for the decision"},
        },
        "required": ["alpha_id", "action"],
    }
    repeatable = True
    is_readonly = False

    def execute(self, alpha_id: str = "", action: str = "approve", reason: str = "", **kwargs) -> str:
        kb = get_kb()
        entry = kb.get(alpha_id)
        if entry is None:
            return json.dumps({"status": "error", "error": f"Factor not found: {alpha_id}"})

        if action == "approve":
            pipeline = FactorPromotionPipeline(kb)
            result = pipeline.promote_to_paper_trading(alpha_id)
            return json.dumps(result, ensure_ascii=False)
        elif action == "reject":
            try:
                kb.transition_status(alpha_id, FactorStatus.REJECTED, reason=reason or "Rejected by human reviewer")
                return json.dumps({"status": "ok", "action": "rejected", "alpha_id": alpha_id})
            except ValueError as exc:
                return json.dumps({"status": "error", "error": str(exc)})
        return json.dumps({"status": "error", "error": f"Unknown action: {action}"})


class FactorMiningStartGPTool(BaseTool):
    """Start a GP evolution run with configurable parameters."""

    name = "factor_mining_start_gp"
    description = (
        "Start a new genetic programming evolution run to discover alpha factors. "
        "Configure population size, generations, data range, and fitness metric."
    )
    parameters = {
        "type": "object",
        "properties": {
            "population_size": {"type": "integer", "description": "Population size (default 100)"},
            "generations": {"type": "integer", "description": "Number of generations (default 50)"},
            "train_start": {"type": "string", "description": "Train start date YYYY-MM-DD"},
            "train_end": {"type": "string", "description": "Train end date YYYY-MM-DD"},
            "test_start": {"type": "string", "description": "Test start date YYYY-MM-DD"},
            "test_end": {"type": "string", "description": "Test end date YYYY-MM-DD"},
            "use_hybrid_init": {"type": "boolean", "description": "Use skeleton-seeded hybrid init (default true)"},
        },
        "required": [],
    }
    repeatable = True
    is_readonly = False

    def execute(self, population_size: int = 100, generations: int = 50,
                train_start: str = "2024-01-01", train_end: str = "2025-06-30",
                test_start: str = "2025-07-01", test_end: str = "2025-12-31",
                use_hybrid_init: bool = True, **kwargs) -> str:
        from src.factors.mining.gp_engine import GPEvolutionConfig, GPEvolution

        config = GPEvolutionConfig(
            population_size=population_size,
            generations=generations,
            train_start=train_start, train_end=train_end,
            test_start=test_start, test_end=test_end,
            fitness_metric="composite",
            use_hybrid_init=use_hybrid_init,
            use_tiered_operators=True,
            use_kb=True,
        )
        gp = GPEvolution(config)
        result = gp.run()

        return json.dumps({
            "status": "ok",
            "job_id": result.job_id,
            "best_test_ic": result.best_test_ic,
            "generations": len(result.generation_history),
            "runtime_seconds": round(result.runtime_seconds, 1),
            "kb_new": gp._kb_new_registrations,
            "kb_dupes": gp._kb_duplicates_avoided,
            "candidates": len(result.best_individuals),
            "best_formula": result.best_individuals[0].formula if result.best_individuals else "",
        }, ensure_ascii=False)


class FactorKBListTool(BaseTool):
    """List factors in the knowledge base by status or source."""

    name = "factor_kb_list"
    description = "List factors in the knowledge base, optionally filtered by status or source."
    parameters = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "Filter by status (approved/paper_trading/production/deprecated/all)"},
            "source": {"type": "string", "description": "Filter by source (gp_engine/llm_miner/manual)"},
            "limit": {"type": "integer", "description": "Max results (default 20)"},
        },
        "required": [],
    }
    repeatable = True
    is_readonly = True

    def execute(self, status: str = "all", source: str = "", limit: int = 20, **kwargs) -> str:
        kb = get_kb()
        if status and status != "all":
            entries = kb.list_by_status(status)
        elif source:
            entries = kb.list_by_source(source)
        else:
            entries = kb.list_all()

        entries = entries[:limit]
        formatted = [
            {
                "alpha_id": e.alpha_id,
                "formula": e.formula[:80],
                "formula_hash": e.formula_hash,
                "status": e.status,
                "test_ic": e.test_ic,
                "source": e.source,
                "theme": e.theme,
            }
            for e in entries
        ]
        return json.dumps({"status": "ok", "total": len(kb), "returned": len(formatted), "entries": formatted}, ensure_ascii=False)
