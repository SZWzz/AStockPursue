"""Base class for all workflow nodes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.workflow.schema import NodeDefinition, NodePort, PortDirection, PortType


class BaseNode(ABC):
    """Abstract base for all workflow nodes.

    Subclasses override class-level attributes.  No dataclass — class attrs
    are read directly from the subclass in :meth:`get_definition`.

    Lifecycle hooks (all optional, all async):
        on_init()        — called once before execute(), for resource acquisition
        on_validate()    — called before execute(), should raise on invalid config
        on_cleanup()     — called after execute() or on cancel, for resource release
        on_cancel()      — called when the engine cancels this node mid-execution
    """

    node_type: str = ""
    category: str = "data"
    label: str = ""
    description: str = ""
    icon: str = "Circle"
    inputs: List[NodePort] = []
    outputs: List[NodePort] = []
    config_schema: Dict[str, Any] = {}
    resource_profile: str = "default"  # default | cpu_bound | io_bound

    version: int = 1                      # bump when node implementation changes (invalidates cache)
    timeout_seconds: float = 600          # per-node timeout override (0 = no timeout)

    # ── Lifecycle hooks (override in subclasses) ─────────────────────────────

    async def on_init(self, config: Dict[str, Any]) -> None:
        """Called once before execute().  Acquire resources here."""
        pass

    async def on_validate(self, inputs: Dict[str, Any], config: Dict[str, Any]) -> None:
        """Called before execute().  Raise ValueError if inputs/config are invalid."""
        pass

    async def on_cleanup(self) -> None:
        """Called after execute() or on cancel.  Release resources here."""
        pass

    async def on_cancel(self) -> None:
        """Called when the engine cancels this node mid-execution."""
        pass

    # ── Core ─────────────────────────────────────────────────────────────────

    @abstractmethod
    async def execute(self, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute this node.  Inputs are resolved Python objects (DataFrames, dicts, …).
        Returns a dict of {port_name: output_value}."""
        ...

    def get_definition(self) -> NodeDefinition:
        return NodeDefinition(
            node_type=self.node_type,
            category=self.category,
            label=self.label,
            description=self.description,
            icon=self.icon,
            inputs=list(self.inputs),
            outputs=list(self.outputs),
            config_schema=dict(self.config_schema),
            resource_profile=self.resource_profile,
        )

    @staticmethod
    def in_port(name: str, t: PortType, required: bool = True, description: str = "") -> NodePort:
        return NodePort(name=name, port_type=t, direction=PortDirection.INPUT, required=required, description=description)

    @staticmethod
    def out_port(name: str, t: PortType, description: str = "") -> NodePort:
        return NodePort(name=name, port_type=t, direction=PortDirection.OUTPUT, required=False, description=description)
