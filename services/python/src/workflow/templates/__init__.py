"""Pre-built strategy workflow templates.

Each template is a {nodes, edges} dict that can be loaded onto the canvas.
Templates represent common strategy patterns that can be auto-detected from
user code and expanded into visual DAGs.

Pipeline presets (presets.py) are complete end-to-end DAG definitions that
return full WorkflowModel instances with all nodes and edges wired.
"""

from .registry import TEMPLATES, match_template, load_template  # noqa: F401 — public API re-exports
from .presets import (  # noqa: F401 — public API re-exports
    PRESET_META,
    PRESET_FACTORIES,
    list_presets,
    load_preset,
    momentum_strategy,
    mean_reversion_strategy,
    multi_factor_strategy,
    pair_trading_strategy,
    factor_mining_pipeline,
)
