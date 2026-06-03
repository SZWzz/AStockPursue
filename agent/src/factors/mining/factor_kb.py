"""Factor Knowledge Base — structured memory for factor lifecycle management.

The FactorKB is the central registry for all discovered factors, whether
from GP evolution, LLM mining, or manual authoring.  It enforces **formula
consistency**: every factor is stored with its canonical ExpressionTree as
the single source of truth, from which the formula string, hash, and
SignalEngine code are derived.

Key capabilities:
    - Register/query factors with formula dedup via SHA256 hash
    - Semantic search (tag-based for now, pgvector-ready schema)
    - Lifecycle state machine: discovered → validating → approved →
      paper_trading → production → deprecated → archived
    - Data source version binding for automatic revalidation
    - Similarity tracking between factors
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from src.factors.mining.expression_tree import ExpressionTree

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifecycle state machine
# ---------------------------------------------------------------------------

class FactorStatus:
    """Factor lifecycle states."""

    DISCOVERED = "discovered"         # Newly generated, not yet validated
    VALIDATING = "validating"         # IC/WF checks in progress
    APPROVED = "approved"             # Statistical validation passed, pending human review
    REJECTED = "rejected"             # Failed validation or human rejection
    PAPER_TRADING = "paper_trading"   # Running in simulated trading
    PRODUCTION = "production"         # Live in Alpha Zoo Core
    DEPRECATED = "deprecated"         # IC decay detected, under observation
    ARCHIVED = "archived"             # Permanently retired

    # Valid transitions
    TRANSITIONS: dict[str, list[str]] = {
        DISCOVERED:   [VALIDATING, REJECTED],
        VALIDATING:   [APPROVED, DISCOVERED, REJECTED],
        APPROVED:     [PAPER_TRADING, REJECTED, DEPRECATED],
        PAPER_TRADING: [PRODUCTION, APPROVED, DEPRECATED],
        PRODUCTION:   [DEPRECATED],
        DEPRECATED:   [APPROVED, ARCHIVED],
        REJECTED:     [DISCOVERED],
        ARCHIVED:     [],  # terminal state
    }

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        return to_status in cls.TRANSITIONS.get(from_status, [])

    @classmethod
    def is_terminal(cls, status: str) -> bool:
        return status == cls.ARCHIVED

    @classmethod
    def is_active(cls, status: str) -> bool:
        return status in (cls.APPROVED, cls.PAPER_TRADING, cls.PRODUCTION)


# ---------------------------------------------------------------------------
# Factor entry
# ---------------------------------------------------------------------------

@dataclass
class FactorEntry:
    """A single factor record in the knowledge base.

    The ``tree`` field is the single source of truth — formula, hash,
    and code are all derived from it.
    """

    # ── Identity (derived from tree) ──
    alpha_id: str                           # Unique identifier
    tree: ExpressionTree                    # ← SINGLE SOURCE OF TRUTH
    formula_hash: str = ""                  # SHA256[:16] of normalized_formula
    formula: str = ""                       # Human-readable (from tree.to_formula())
    normalized_formula: str = ""            # Canonical (from tree.normalized_formula)

    # ── Metadata ──
    name: str = ""
    theme: list[str] = field(default_factory=list)
    semantic_tags: list[str] = field(default_factory=list)
    source: str = ""                        # "gp_engine" / "llm_miner" / "manual"
    source_prompt: str = ""
    economic_rationale: str = ""
    data_source_version: str = ""

    # ── Performance metrics ──
    train_ic: float = 0.0
    test_ic: float = 0.0
    test_ir: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    ic_decay_halflife: float | None = None
    oos_ic_per_window: list[float] = field(default_factory=list)

    # ── Orthogonality ──
    orthogonality_score: float = 0.0
    max_corr_with_core: float = 0.0

    # ── Lifecycle ──
    status: str = FactorStatus.DISCOVERED
    discovered_at: str = ""
    last_validated_at: str = ""
    archived_at: str = ""
    archived_reason: str = ""

    # ── Complexity ──
    complexity: int = 0

    def __post_init__(self):
        """Derive formula representations from the tree (single source of truth)."""
        if not self.formula_hash:
            self.formula_hash = self.tree.formula_hash
        if not self.formula:
            self.formula = self.tree.to_formula()
        if not self.normalized_formula:
            self.normalized_formula = self.tree.normalized_formula
        if not self.complexity:
            self.complexity = self.tree.complexity()
        if not self.discovered_at:
            self.discovered_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "alpha_id": self.alpha_id,
            "formula_hash": self.formula_hash,
            "formula": self.formula,
            "normalized_formula": self.normalized_formula,
            "expression_json": self.tree.to_dict(),
            "name": self.name,
            "theme": self.theme,
            "semantic_tags": self.semantic_tags,
            "source": self.source,
            "source_prompt": self.source_prompt,
            "economic_rationale": self.economic_rationale,
            "data_source_version": self.data_source_version,
            "train_ic": self.train_ic,
            "test_ic": self.test_ic,
            "test_ir": self.test_ir,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "ic_decay_halflife": self.ic_decay_halflife,
            "oos_ic_per_window": self.oos_ic_per_window,
            "orthogonality_score": self.orthogonality_score,
            "max_corr_with_core": self.max_corr_with_core,
            "status": self.status,
            "discovered_at": self.discovered_at,
            "last_validated_at": self.last_validated_at,
            "archived_at": self.archived_at,
            "archived_reason": self.archived_reason,
            "complexity": self.complexity,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FactorEntry:
        """Deserialize from dict, reconstructing the ExpressionTree as source of truth."""
        tree = ExpressionTree.from_dict(d["expression_json"])
        return cls(
            alpha_id=d.get("alpha_id", ""),
            tree=tree,
            name=d.get("name", ""),
            theme=d.get("theme", []),
            semantic_tags=d.get("semantic_tags", []),
            source=d.get("source", ""),
            source_prompt=d.get("source_prompt", ""),
            economic_rationale=d.get("economic_rationale", ""),
            data_source_version=d.get("data_source_version", ""),
            train_ic=d.get("train_ic", 0.0),
            test_ic=d.get("test_ic", 0.0),
            test_ir=d.get("test_ir", 0.0),
            sharpe=d.get("sharpe", 0.0),
            max_drawdown=d.get("max_drawdown", 0.0),
            ic_decay_halflife=d.get("ic_decay_halflife"),
            oos_ic_per_window=d.get("oos_ic_per_window", []),
            orthogonality_score=d.get("orthogonality_score", 0.0),
            max_corr_with_core=d.get("max_corr_with_core", 0.0),
            status=d.get("status", FactorStatus.DISCOVERED),
            discovered_at=d.get("discovered_at", ""),
            last_validated_at=d.get("last_validated_at", ""),
            archived_at=d.get("archived_at", ""),
            archived_reason=d.get("archived_reason", ""),
            complexity=d.get("complexity", 0),
        )


# ---------------------------------------------------------------------------
# Factor Knowledge Base
# ---------------------------------------------------------------------------

class FactorKnowledgeBase:
    """In-memory factor knowledge base with lifecycle management.

    Thread-safe for single-process use.  Designed to be backed by
    PostgreSQL/pgvector in production — the API surface stays the same.
    """

    def __init__(self, user_id: int = 1) -> None:
        self._user_id = user_id
        self._entries: dict[str, FactorEntry] = {}        # alpha_id → entry
        self._by_hash: dict[str, str] = {}                 # formula_hash → alpha_id
        self._by_status: dict[str, list[str]] = {s: [] for s in (
            FactorStatus.DISCOVERED, FactorStatus.VALIDATING, FactorStatus.APPROVED,
            FactorStatus.REJECTED, FactorStatus.PAPER_TRADING, FactorStatus.PRODUCTION,
            FactorStatus.DEPRECATED, FactorStatus.ARCHIVED,
        )}
        self._by_source_version: dict[str, list[str]] = {}  # source_version → [alpha_id, …]

    # ------------------------------------------------------------------
    # Registration (with formula dedup)
    # ------------------------------------------------------------------

    def register(
        self,
        tree: ExpressionTree,
        *,
        alpha_id: str | None = None,
        name: str = "",
        theme: list[str] | None = None,
        semantic_tags: list[str] | None = None,
        source: str = "unknown",
        source_prompt: str = "",
        economic_rationale: str = "",
        data_source_version: str = "",
        **metrics,
    ) -> tuple[FactorEntry, bool]:
        """Register a new factor in the knowledge base.

        **Formula dedup**: if a factor with the same ``formula_hash`` already
        exists, returns the existing entry with ``is_new=False``.

        Args:
            tree: ExpressionTree — the single source of truth for the formula.
            alpha_id: Optional custom ID (auto-generated if None).
            name: Human-readable factor name.
            theme: Theme categories (e.g. ["momentum", "volume"]).
            semantic_tags: LLM-generated semantic tags.
            source: Origin of the factor (gp_engine / llm_miner / manual).
            source_prompt: Prompt that generated this factor (for traceability).
            economic_rationale: Economic intuition behind the factor.
            data_source_version: Version of the data source used.
            **metrics: Performance metrics (train_ic, test_ic, sharpe, etc.).

        Returns:
            (entry, is_new) — entry is the FactorEntry, is_new is False if
            a duplicate was found.
        """
        fhash = tree.formula_hash

        # ── Dedup check ──
        if fhash in self._by_hash:
            existing_id = self._by_hash[fhash]
            return self._entries[existing_id], False

        # ── Generate unique ID ──
        if alpha_id is None:
            alpha_id = f"factor_{fhash}"
        # Ensure uniqueness
        base_id = alpha_id
        counter = 1
        while alpha_id in self._entries:
            alpha_id = f"{base_id}_{counter}"
            counter += 1

        # ── Create entry ──
        # [P3-02 fix] Normalize themes to lowercase so "Momentum" and
        # "momentum" are treated as the same theme across registrations
        # and get_mining_guidance() comparisons.
        entry = FactorEntry(
            alpha_id=alpha_id,
            tree=tree,
            name=name or alpha_id,
            theme=[t.lower() for t in (theme or [])],
            semantic_tags=[t.lower() for t in (semantic_tags or [])],
            source=source,
            source_prompt=source_prompt,
            economic_rationale=economic_rationale,
            data_source_version=data_source_version,
            train_ic=metrics.get("train_ic", 0.0),
            test_ic=metrics.get("test_ic", 0.0),
            test_ir=metrics.get("test_ir", 0.0),
            sharpe=metrics.get("sharpe", 0.0),
            max_drawdown=metrics.get("max_drawdown", 0.0),
            ic_decay_halflife=metrics.get("ic_decay_halflife"),
            oos_ic_per_window=metrics.get("oos_ic_per_window", []),
            orthogonality_score=metrics.get("orthogonality_score", 0.0),
            max_corr_with_core=metrics.get("max_corr_with_core", 0.0),
            status=FactorStatus.DISCOVERED,
        )

        # ── Index ──
        self._entries[alpha_id] = entry
        self._by_hash[fhash] = alpha_id
        self._by_status[entry.status].append(alpha_id)

        # Data source version index
        if data_source_version:
            self._by_source_version.setdefault(data_source_version, []).append(alpha_id)

        logger.info("FactorKB: registered %s (hash=%s, source=%s)", alpha_id, fhash, source)
        return entry, True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, alpha_id: str) -> FactorEntry | None:
        """Retrieve a factor by its alpha_id."""
        return self._entries.get(alpha_id)

    def get_by_hash(self, formula_hash: str) -> FactorEntry | None:
        """Retrieve a factor by its formula_hash."""
        alpha_id = self._by_hash.get(formula_hash)
        if alpha_id:
            return self._entries.get(alpha_id)
        return None

    def list_by_status(self, status: str) -> list[FactorEntry]:
        """List all factors with a given lifecycle status."""
        ids = self._by_status.get(status, [])
        return [self._entries[i] for i in ids if i in self._entries]

    def list_active(self) -> list[FactorEntry]:
        """List all active (approved/paper_trading/production) factors."""
        result: list[FactorEntry] = []
        for s in (FactorStatus.APPROVED, FactorStatus.PAPER_TRADING, FactorStatus.PRODUCTION):
            result.extend(self.list_by_status(s))
        return result

    def list_by_source(self, source: str) -> list[FactorEntry]:
        """List factors by their source (gp_engine / llm_miner / manual)."""
        return [e for e in self._entries.values() if e.source == source]

    def list_all(self) -> list[FactorEntry]:
        """List all registered factors."""
        return list(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, alpha_id: str) -> bool:
        return alpha_id in self._entries

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    def transition_status(
        self,
        alpha_id: str,
        new_status: str,
        reason: str = "",
    ) -> bool:
        """Transition a factor to a new lifecycle status.

        Args:
            alpha_id: Factor ID.
            new_status: Target status (must be a valid transition).
            reason: Human-readable reason for the transition.

        Returns:
            True if the transition was successful.

        Raises:
            ValueError: If the transition is invalid.
        """
        entry = self._entries.get(alpha_id)
        if entry is None:
            raise ValueError(f"Factor not found: {alpha_id}")

        old_status = entry.status
        if not FactorStatus.can_transition(old_status, new_status):
            raise ValueError(
                f"Invalid status transition: {old_status} → {new_status}. "
                f"Allowed: {FactorStatus.TRANSITIONS.get(old_status, [])}"
            )

        # Update indexes
        self._by_status[old_status].remove(alpha_id)
        self._by_status[new_status].append(alpha_id)

        # Update entry
        entry.status = new_status
        now = datetime.now(timezone.utc).isoformat()
        if new_status == FactorStatus.ARCHIVED:
            entry.archived_at = now
            entry.archived_reason = reason
        elif new_status == FactorStatus.VALIDATING:
            entry.last_validated_at = now

        logger.info("FactorKB: %s %s → %s (reason: %s)", alpha_id, old_status, new_status, reason or "n/a")
        return True

    def auto_deprecate(
        self,
        ic_threshold: float = 0.01,
        consecutive_months: int = 3,
    ) -> list[str]:
        """Automatically deprecate factors with sustained low IC.

        This is a heuristic — in production, the actual IC would come
        from periodic snapshots in ``vt_factor_performance_snapshots``.

        Returns:
            List of alpha_ids that were deprecated.
        """
        deprecated: list[str] = []
        for entry in self.list_active():
            if abs(entry.test_ic) < ic_threshold:
                self.transition_status(entry.alpha_id, FactorStatus.DEPRECATED,
                                       reason=f"IC {entry.test_ic:.4f} below threshold {ic_threshold}")
                deprecated.append(entry.alpha_id)
        return deprecated

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_by_tags(
        self,
        tags: list[str],
        top_k: int = 10,
    ) -> list[FactorEntry]:
        """Search factors by semantic tag overlap (Jaccard similarity).

        Args:
            tags: Query tags (e.g. ["低换手率", "价值反转"]).
            top_k: Max results to return.

        Returns:
            Factors sorted by tag overlap score descending.
        """
        query_set = set(t.lower() for t in tags)
        if not query_set:
            return []

        scored: list[tuple[float, FactorEntry]] = []
        for entry in self._entries.values():
            if entry.status == FactorStatus.ARCHIVED:
                continue
            entry_tags = set(t.lower() for t in entry.semantic_tags + entry.theme)
            if not entry_tags:
                continue
            # Jaccard similarity
            intersection = query_set & entry_tags
            union = query_set | entry_tags
            score = len(intersection) / len(union) if union else 0.0
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    def search_by_formula_similarity(
        self,
        tree: ExpressionTree,
        top_k: int = 10,
    ) -> list[tuple[float, FactorEntry]]:
        """Find factors with structurally similar formulas.

        Uses a simple approach: compare normalized formula substrings.
        In production, this would use pgvector cosine similarity on
        formula_embedding.

        Args:
            tree: Query expression tree.
            top_k: Max results to return.

        Returns:
            List of (similarity_score, FactorEntry) sorted by score descending.
        """
        query_norm = tree.normalized_formula
        query_parts = set(query_norm.replace("(", " ").replace(")", " ").replace(",", " ").split())

        scored: list[tuple[float, FactorEntry]] = []
        for entry in self._entries.values():
            if entry.formula_hash == tree.formula_hash:
                continue  # skip self
            entry_parts = set(
                entry.normalized_formula.replace("(", " ").replace(")", " ").replace(",", " ").split()
            )
            if not query_parts or not entry_parts:
                continue
            overlap = query_parts & entry_parts
            score = len(overlap) / max(len(query_parts), len(entry_parts))
            if score > 0.3:  # minimum structural similarity threshold
                scored.append((round(score, 4), entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Core factor selection (for orthogonality checks)
    # ------------------------------------------------------------------

    def get_top_core_factors(self, n: int = 50) -> list[FactorEntry]:
        """Return the top-N core factors for orthogonality reference.

        Core factors are those in PRODUCTION or PAPER_TRADING status,
        sorted by test_ic descending.
        """
        core = [
            e for e in self._entries.values()
            if e.status in (FactorStatus.PRODUCTION, FactorStatus.PAPER_TRADING, FactorStatus.APPROVED)
        ]
        core.sort(key=lambda e: abs(e.test_ic), reverse=True)
        return core[:n]

    # ------------------------------------------------------------------
    # Data source version binding
    # ------------------------------------------------------------------

    def on_data_source_change(
        self,
        source_name: str,
        old_version: str,
        new_version: str,
    ) -> list[str]:
        """Trigger revalidation of factors affected by a data source change.

        Args:
            source_name: Name of the data source that changed.
            old_version: Previous version string.
            new_version: New version string.

        Returns:
            List of alpha_ids queued for revalidation.
        """
        affected: list[str] = []
        for entry in self._entries.values():
            if not FactorStatus.is_active(entry.status):
                continue
            if source_name.lower() in entry.data_source_version.lower():
                try:
                    self.transition_status(
                        entry.alpha_id,
                        FactorStatus.VALIDATING,
                        reason=f"Data source changed: {source_name} {old_version} → {new_version}",
                    )
                    affected.append(entry.alpha_id)
                except ValueError:
                    pass

        if affected:
            logger.warning(
                "Data source %s changed (%s → %s), %d factors queued for revalidation",
                source_name, old_version, new_version, len(affected),
            )
        return affected

    # ------------------------------------------------------------------
    # Mining guidance (for LLM/GP feedback loop)
    # ------------------------------------------------------------------

    def get_mining_guidance(self) -> dict[str, Any]:
        """Generate guidance for the next round of factor mining.

        Analyses which themes are alive/dead in the Zoo, which themes
        have room for new factors, and which are saturated.

        Returns:
            Dict with guidance for LLM prompt and GP fitness weights.
        """
        alive_themes: dict[str, int] = {}
        dead_themes: dict[str, int] = {}
        theme_ics: dict[str, list[float]] = {}

        for entry in self._entries.values():
            for theme in entry.theme:
                theme_lower = theme.lower()
                if entry.status in (FactorStatus.PRODUCTION, FactorStatus.PAPER_TRADING, FactorStatus.APPROVED):
                    alive_themes[theme_lower] = alive_themes.get(theme_lower, 0) + 1
                    theme_ics.setdefault(theme_lower, []).append(abs(entry.test_ic))
                elif entry.status in (FactorStatus.DEPRECATED, FactorStatus.ARCHIVED):
                    dead_themes[theme_lower] = dead_themes.get(theme_lower, 0) + 1

        # Theme health: mean IC of alive factors in each theme
        theme_health = {}
        for theme, ics in theme_ics.items():
            if ics:
                theme_health[theme] = {
                    "count": alive_themes.get(theme, 0),
                    "mean_ic": round(float(np.mean(ics)), 4),
                    "trend": "rising" if np.mean(ics) > 0.025 else "stable" if np.mean(ics) > 0.01 else "declining",
                }

        # Themes to avoid (high dead/alive ratio)
        avoid_themes = []
        for theme in dead_themes:
            alive_count = alive_themes.get(theme, 0)
            dead_count = dead_themes[theme]
            if dead_count > 0 and dead_count >= alive_count * 2:
                avoid_themes.append(theme)

        # Themes with room (few alive factors)
        explore_themes = [t for t, h in theme_health.items() if h["count"] < 5 and h["mean_ic"] > 0.01]

        return {
            "theme_health": theme_health,
            "avoid_themes": avoid_themes,
            "explore_themes": explore_themes,
            "total_active": sum(alive_themes.values()),
            "total_dead": sum(dead_themes.values()),
        }

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dicts(self) -> list[dict[str, Any]]:
        """Export all entries as JSON-serializable dicts."""
        return [e.to_dict() for e in self._entries.values()]

    def save(self, path: str) -> None:
        """Persist the knowledge base to a JSON file."""
        import json
        data = {
            "user_id": self._user_id,
            "entries": self.to_dicts(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info("FactorKB saved to %s (%d entries)", path, len(self._entries))

    @classmethod
    def load(cls, path: str, user_id: int = 1) -> FactorKnowledgeBase:
        """Load the knowledge base from a JSON file."""
        import json
        kb = cls(user_id=user_id)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry_dict in data.get("entries", []):
            try:
                tree = ExpressionTree.from_dict(entry_dict["expression_json"])
                entry = FactorEntry.from_dict(entry_dict)
                entry.tree = tree  # Ensure consistency
                kb._entries[entry.alpha_id] = entry
                kb._by_hash[entry.formula_hash] = entry.alpha_id
                kb._by_status[entry.status].append(entry.alpha_id)
                if entry.data_source_version:
                    kb._by_source_version.setdefault(entry.data_source_version, []).append(entry.alpha_id)
            except Exception as exc:
                logger.warning("Failed to load factor entry: %s", exc)
        logger.info("FactorKB loaded from %s (%d entries)", path, len(kb._entries))
        return kb


# ---------------------------------------------------------------------------
# Singleton accessor (module-level)
# ---------------------------------------------------------------------------

_default_kb: FactorKnowledgeBase | None = None


def get_kb(user_id: int = 1) -> FactorKnowledgeBase:
    """Get or create the default FactorKnowledgeBase instance."""
    global _default_kb
    if _default_kb is None:
        _default_kb = FactorKnowledgeBase(user_id=user_id)
    return _default_kb
