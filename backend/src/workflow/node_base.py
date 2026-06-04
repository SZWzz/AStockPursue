"""Base class for all workflow nodes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.workflow.schema import NodeDefinition, NodePort, PortDirection, PortType


class BaseNode(ABC):
    """Abstract base for all workflow nodes.

    Subclasses override class-level attributes.  No dataclass — class attrs
    are read directly from the subclass in :meth:`get_definition`.
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
