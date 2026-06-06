"""Node type registry — explicit registration, no auto-discover magic."""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from src.workflow.node_base import BaseNode
from src.workflow.schema import NodeDefinition, PortType, is_compatible


class NodeRegistry:
    """Central registry of all available node types."""

    def __init__(self):
        self._nodes: Dict[str, Type[BaseNode]] = {}
        self._definitions: Dict[str, NodeDefinition] = {}

    def register(self, node_cls: Type[BaseNode]) -> Type[BaseNode]:
        nt = node_cls.node_type
        if not nt:
            raise ValueError(f"Node class {node_cls.__name__} has empty node_type")
        self._nodes[nt] = node_cls
        self._definitions[nt] = node_cls().get_definition()
        return node_cls

    def get(self, node_type: str) -> NodeDefinition:
        if node_type not in self._definitions:
            raise KeyError(f"Unknown node type: {node_type!r}")
        return self._definitions[node_type]

    def get_class(self, node_type: str) -> Type[BaseNode]:
        if node_type not in self._nodes:
            raise KeyError(f"Unknown node type: {node_type!r}")
        return self._nodes[node_type]

    def list_all(self) -> List[NodeDefinition]:
        return list(self._definitions.values())

    def get_compatible_targets(self, source_port_type: PortType) -> List[NodeDefinition]:
        result = []
        for d in self._definitions.values():
            for port in d.inputs:
                if is_compatible(source_port_type, port.port_type):
                    result.append(d)
                    break
        return result

    def validate_connection(self, source_type: PortType, target_type: PortType) -> bool:
        return is_compatible(source_type, target_type)


# ── Singleton ─────────────────────────────────────────────────────────────────

_registry: Optional[NodeRegistry] = None


def get_node_registry() -> NodeRegistry:
    global _registry
    if _registry is None:
        _registry = NodeRegistry()
    return _registry


def register_node(cls: Type[BaseNode]) -> Type[BaseNode]:
    return get_node_registry().register(cls)


def init_workflow_nodes():
    """Explicitly import all node modules to trigger @register_node decorators.

    Called once at API server startup.  No auto-discover magic.
    """
    from src.workflow.nodes import data_nodes       # noqa: F401
    from src.workflow.nodes import alpha_nodes      # noqa: F401
    from src.workflow.nodes import strategy_nodes   # noqa: F401
    from src.workflow.nodes import analysis_nodes   # noqa: F401
    from src.workflow.nodes import thin_nodes       # noqa: F401
    from src.workflow.nodes import control_nodes    # noqa: F401
    from src.workflow.nodes import correlation_nodes   # noqa: F401
    from src.workflow.nodes import indicator_nodes     # noqa: F401
    from src.workflow.nodes import comparison_nodes    # noqa: F401
    from src.workflow.nodes import sentiment_nodes     # noqa: F401
    from src.workflow.nodes import mining_nodes        # noqa: F401
    from src.workflow.nodes import trading_nodes       # noqa: F401
    from src.workflow.nodes import options_nodes       # noqa: F401
    from src.workflow.nodes import sector_nodes        # noqa: F401
    from src.workflow.nodes import output_nodes        # noqa: F401
    from src.workflow.nodes import factor_atoms        # noqa: F401
    from src.workflow.nodes import signal_nodes        # noqa: F401
