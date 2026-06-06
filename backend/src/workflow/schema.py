"""Schema definitions for the workflow system.

Port types use a flat enum.  Nodes pass DataFrames directly in memory — no
serialization layer needed since workflow execution is single-process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


# ── Enums ─────────────────────────────────────────────────────────────────────

class PortDirection(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CACHED = "cached"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PortType(str, Enum):
    """Flat port types.  Nodes pass typed data through typed ports."""
    STOCK_LIST = "stock_list"           # list[str]
    DATE_RANGE = "date_range"           # (start, end)
    PARAMS = "params"                   # dict[str, Any]
    BOOL = "bool"

    DF_OHLCV = "df_ohlcv"              # {code: DataFrame(o,h,l,c,v)}
    DF_FACTOR = "df_factor"            # DataFrame: index=date, columns=codes
    DF_RETURNS = "df_returns"

    FACTOR_RESULT = "factor_result"    # dict with IC stats
    SIGNAL = "signal"                  # dict[code, weight/Series]
    BACKTEST_RESULT = "backtest_result"
    ATTRIBUTION = "attribution"

    TECHNICAL_INDICATOR = "technical_indicator"    # IndicatorNode output
    CORRELATION_MATRIX = "correlation_matrix"      # CorrelationNode output
    SENTIMENT = "sentiment"                         # NewsSentimentNode output
    COMPARISON_RESULT = "comparison_result"         # ComparisonNode output

    NOTIFY_CONFIG = "notify_config"                 # Notification config dict
    ORDER_RESULT = "order_result"                   # Order execution result dict
    REGIME_RESULT = "regime_result"                 # Market regime detection dict
    EXPERIMENT_RESULT = "experiment_result"         # Experiment output dict
    SCORE_RESULT = "score_result"                   # Strategy scoring result dict

    ANY = "any"                        # Wildcard — accepts anything


# Compatibility: same type or wildcard
def is_compatible(source: PortType, target: PortType) -> bool:
    if target == PortType.ANY or source == target:
        return True
    return False


# ── Node models ───────────────────────────────────────────────────────────────

@dataclass
class NodePort:
    name: str
    port_type: PortType
    direction: PortDirection
    required: bool = True
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name, "port_type": self.port_type.value,
            "direction": self.direction.value, "required": self.required,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NodePort":
        return cls(
            name=d["name"], port_type=PortType(d["port_type"]),
            direction=PortDirection(d["direction"]),
            required=d.get("required", True), description=d.get("description", ""),
        )


@dataclass
class NodeDefinition:
    node_type: str
    category: str       # data | alpha | filter | strategy | execution | analysis | deploy | control | output
    label: str
    description: str = ""
    icon: str = "Circle"
    inputs: List[NodePort] = field(default_factory=list)
    outputs: List[NodePort] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    resource_profile: str = "default"  # default | cpu_bound | io_bound

    def to_dict(self) -> dict:
        return {
            "node_type": self.node_type, "category": self.category,
            "label": self.label, "description": self.description,
            "icon": self.icon, "inputs": [p.to_dict() for p in self.inputs],
            "outputs": [p.to_dict() for p in self.outputs],
            "config_schema": self.config_schema,
            "resource_profile": self.resource_profile,
        }


# ── Workflow DAG ──────────────────────────────────────────────────────────────

@dataclass
class WorkflowModel:
    """Full workflow definition — nodes, edges, viewport, and metadata."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    user_id: int = 0
    name: str = ""
    description: str = ""
    nodes: List[WorkflowNodeData] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    viewport: Dict[str, Any] = field(default_factory=lambda: {"x": 0, "y": 0, "zoom": 1})
    is_locked: bool = False
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "project_id": self.project_id,
            "user_id": self.user_id, "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "viewport": self.viewport, "is_locked": self.is_locked,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }


@dataclass
class WorkflowNodeData:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_type: str = ""
    label: str = ""
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0})
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "node_type": self.node_type,
            "label": self.label, "position": self.position,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorkflowNodeData":
        return cls(
            id=d.get("id", str(uuid.uuid4())), node_type=d.get("node_type", ""),
            label=d.get("label", ""), position=d.get("position", {"x": 0, "y": 0}),
            config=d.get("config", {}),
        )


@dataclass
class WorkflowEdge:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    source_port: str = ""
    target: str = ""
    target_port: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "source": self.source, "source_port": self.source_port,
            "target": self.target, "target_port": self.target_port,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorkflowEdge":
        return cls(
            id=d.get("id", str(uuid.uuid4())), source=d.get("source", ""),
            source_port=d.get("source_port", ""), target=d.get("target", ""),
            target_port=d.get("target_port", ""),
        )


# ── Execution records ─────────────────────────────────────────────────────────

@dataclass
class NodeRunResult:
    node_id: str = ""
    status: NodeStatus = NodeStatus.PENDING
    summary: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id, "status": self.status.value,
            "summary": self.summary, "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NodeRunResult":
        return cls(
            node_id=d.get("node_id", ""),
            status=NodeStatus(d["status"]) if "status" in d else NodeStatus.PENDING,
            summary=d.get("summary", {}),
            error_message=d.get("error_message", ""),
            duration_ms=d.get("duration_ms", 0),
        )


@dataclass
class WorkflowRun:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    user_id: int = 0
    status: RunStatus = RunStatus.PENDING
    target_node_id: Optional[str] = None
    snapshot_nodes: List[WorkflowNodeData] = field(default_factory=list)
    snapshot_edges: List[WorkflowEdge] = field(default_factory=list)
    node_results: Dict[str, NodeRunResult] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "workflow_id": self.workflow_id,
            "user_id": self.user_id, "status": self.status.value,
            "target_node_id": self.target_node_id,
            "snapshot_nodes": [n.to_dict() for n in self.snapshot_nodes],
            "snapshot_edges": [e.to_dict() for e in self.snapshot_edges],
            "node_results": {k: v.to_dict() for k, v in self.node_results.items()},
            "started_at": self.started_at, "finished_at": self.finished_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorkflowRun":
        return cls(
            id=d.get("id", str(uuid.uuid4())), workflow_id=d.get("workflow_id", ""),
            user_id=d.get("user_id", 0),
            status=RunStatus(d["status"]) if "status" in d else RunStatus.PENDING,
            target_node_id=d.get("target_node_id"),
            snapshot_nodes=[WorkflowNodeData.from_dict(n) for n in d.get("snapshot_nodes", [])],
            snapshot_edges=[WorkflowEdge.from_dict(e) for e in d.get("snapshot_edges", [])],
            node_results={k: NodeRunResult.from_dict(v) for k, v in d.get("node_results", {}).items()},
            started_at=d.get("started_at", ""), finished_at=d.get("finished_at", ""),
            created_at=d.get("created_at", ""),
        )
