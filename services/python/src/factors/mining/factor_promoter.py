"""Factor promoter: promote validated AI-discovered factors into Alpha Zoo.

Generates standard Alpha Zoo module files following the exact contract:
    __alpha_meta__ dict literal
    compute(panel: dict[str, pd.DataFrame]) -> pd.DataFrame
"""

from __future__ import annotations

import logging
import textwrap
from datetime import datetime, timezone
from pathlib import Path


from src.factors.mining.expression_tree import ExpressionTree
from src.factors.mining.gp_engine import GPIndividual

logger = logging.getLogger(__name__)

ZOO_MINING_DIR = Path(__file__).resolve().parent.parent / "zoo" / "mined"

TEMPLATE = '''"""AI-mined alpha factor: {name}.

Discovered by: {source}
Discovery date: {date}
Formula: {formula}
Description: {description}
Test IC: {test_ic:.4f}
Test IR: {test_ir:.2f}
Complexity: {complexity}
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any

__alpha_meta__ = {{
    "id": "{alpha_id}",
    "nickname": "{name}",
    "theme": {themes},
    "formula_latex": r"{latex}",
    "columns_required": {columns_required},
    "universe": {universes},
    "frequency": ["daily"],
    "decay_horizon": 5,
    "min_warmup_bars": 21,
    "notes": \"\"\"AI-mined factor: {formula}

{description}

Source: {source}
Test IC: {test_ic:.4f}, Test IR: {test_ir:.2f}
Discovered: {date}
\"\"\",
}}


def compute(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    \"\"\"Compute the factor values from a panel of wide DataFrames.

    Formula: {formula}

    Args:
        panel: Dict mapping column names to wide DataFrames
               (index=dates, columns=codes). Must contain keys: {columns_required}.

    Returns:
        Wide DataFrame of factor values (same shape as panel['close']).
    \"\"\"
    # === Implementation ===
{implementation}

    # === Final cleanup ===
    result = result.replace([np.inf, -np.inf], np.nan)
    if "close" in panel:
        result = result.reindex_like(panel["close"])
    return result
'''


class FactorPromoter:
    """Promotes AI-discovered factors into the Alpha Zoo."""

    def _generate_implementation(self, formula: str) -> str:
        """Generate the compute() function body from a formula string."""
        lines = textwrap.dedent("""
    # Factor values computed from panel data
    close = panel.get("close")
    if close is None:
        raise ValueError("Factor requires 'close' in panel")

    open_ = panel.get("open")
    high = panel.get("high")
    low = panel.get("low")
    volume = panel.get("volume")

    # Derived components
    returns_1d = close.pct_change(1)
    returns_5d = close.pct_change(5)
    returns_20d = close.pct_change(20)

    # === Factor formula ===
    result = $FORMULA

    return result
""")
        lines = lines.replace("$FORMULA", formula)
        return textwrap.indent(lines, "    ")

    def promote(
        self,
        individual: GPIndividual,
        name: str = "",
        theme: str = "momentum",
        universe: str = "equity_cn",
        description: str = "",
        source: str = "gp_engine",
    ) -> str:
        """Generate a Python file for the promoted factor and write it to zoo/mined/.

        Args:
            individual: The GP individual to promote.
            name: Human-readable name for the factor.
            theme: Factor theme (momentum, value, etc.).
            universe: Target universe (equity_cn, equity_us, etc.).
            description: Optional description.
            source: Source of the factor (gp_engine, llm_miner, hybrid).

        Returns:
            The alpha_id of the promoted factor.
        """
        formula = individual.formula
        alpha_id = f"mined_{name}" if name else f"mined_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        alpha_id = alpha_id.lower().replace(" ", "_").replace("-", "_")

        # Determine themes and columns from the formula
        themes = [theme] if theme else ["momentum"]
        columns_required = ["close"]
        if any(kw in formula for kw in ["open", "high", "low"]):
            columns_required.extend(["open", "high", "low"])
        if "volume" in formula:
            columns_required.append("volume")
        columns_required = sorted(set(columns_required))

        # Generate the file content
        content = TEMPLATE.format(
            name=name or alpha_id,
            source=source,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            formula=formula,
            description=description or f"AI-discovered factor via {source}",
            test_ic=individual.test_ic,
            test_ir=individual.test_ir,
            complexity=individual.complexity,
            alpha_id=alpha_id,
            themes=themes,
            latex=formula.replace("_", "\\_"),
            columns_required=columns_required,
            universes=[universe],
            implementation=self._generate_implementation(formula),
        )

        # Write to zoo/mined/
        ZOO_MINING_DIR.mkdir(parents=True, exist_ok=True)
        file_path = ZOO_MINING_DIR / f"{alpha_id}.py"
        file_path.write_text(content, encoding="utf-8")
        logger.info("Promoted factor %s to %s", alpha_id, file_path)

        return alpha_id

    def promote_from_candidate(
        self,
        formula: str,
        name: str = "",
        theme: str = "momentum",
        universe: str = "equity_cn",
        description: str = "",
        source: str = "llm_miner",
        test_ic: float = 0.0,
        test_ir: float = 0.0,
        complexity: int = 0,
    ) -> str:
        """Promote a factor from a string formula (LLM-discovered).

        Returns:
            The alpha_id of the promoted factor.
        """
        # Create a minimal GPIndividual wrapper
        individual = GPIndividual(
            tree=ExpressionTree.__new__(ExpressionTree),
            test_ic=test_ic,
            test_ir=test_ir,
        )
        # Patch the formula property
        individual.formula = formula  # type: ignore[attr-defined]
        individual.complexity = complexity  # type: ignore[attr-defined]

        return self.promote(
            individual=individual,
            name=name,
            theme=theme,
            universe=universe,
            description=description,
            source=source,
        )
