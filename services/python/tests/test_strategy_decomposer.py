"""Unit tests for strategy decomposer — JSON extraction and validation logic.

Tests the pure functions (_extract_workflow_json, _validate_workflow) without
requiring an actual LLM.  The decompose_strategy function itself requires a
live agent loop and is tested via integration tests.
"""

from __future__ import annotations

import json

import pytest

from src.workflow.strategy_decomposer import (
    _extract_workflow_json,
    _validate_workflow,
    get_node_catalog,
)
from src.workflow.node_registry import get_node_registry, init_workflow_nodes


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module", autouse=True)
def _init_registry():
    """Ensure node registry is populated before tests."""
    registry = get_node_registry()
    if not registry.list_all():
        init_workflow_nodes()


def _valid_workflow() -> dict:
    """Return a minimal valid workflow with an OHLCV → MA pipeline."""
    return {
        "nodes": [
            {
                "id": "n_data",
                "node_type": "column_extract",
                "label": "close",
                "position": {"x": 0, "y": 0},
                "config": {"column": "close"},
            },
            {
                "id": "n_ma",
                "node_type": "ma",
                "label": "MA(5)",
                "position": {"x": 260, "y": 0},
                "config": {"window": 5},
            },
        ],
        "edges": [
            {
                "id": "e1",
                "source": "n_data",
                "source_port": "series",
                "target": "n_ma",
                "target_port": "series",
            },
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_workflow_json
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractWorkflowJson:
    def test_direct_json(self):
        """Plain JSON with nodes and edges keys."""
        wf = _valid_workflow()
        result = _extract_workflow_json(json.dumps(wf))
        assert result is not None
        assert result["nodes"] == wf["nodes"]
        assert result["edges"] == wf["edges"]

    def test_json_with_extra_whitespace(self):
        wf = _valid_workflow()
        result = _extract_workflow_json("  \n " + json.dumps(wf) + "\n  ")
        assert result is not None

    def test_code_block_json(self):
        """JSON inside a markdown ```json code block."""
        wf = _valid_workflow()
        response = f"Here is the workflow:\n\n```json\n{json.dumps(wf)}\n```\n\nDone."
        result = _extract_workflow_json(response)
        assert result is not None
        assert result["nodes"] == wf["nodes"]

    def test_code_block_no_lang(self):
        """JSON inside a plain ``` code block (no language specifier)."""
        wf = _valid_workflow()
        response = f"```\n{json.dumps(wf)}\n```"
        result = _extract_workflow_json(response)
        assert result is not None

    def test_mixed_text_with_json(self):
        """JSON object found among surrounding text via regex."""
        wf = _valid_workflow()
        response = f"Some text before {{\"nodes\": {json.dumps(wf['nodes'])}, \"edges\": {json.dumps(wf['edges'])}}} and after"
        result = _extract_workflow_json(response)
        assert result is not None
        assert len(result["nodes"]) == 2

    def test_no_json_returns_none(self):
        result = _extract_workflow_json("This is just plain text, no JSON here.")
        assert result is None

    def test_missing_edges_key_returns_none(self):
        result = _extract_workflow_json('{"nodes": [], "other": true}')
        assert result is None

    def test_missing_nodes_key_returns_none(self):
        result = _extract_workflow_json('{"edges": [], "other": true}')
        assert result is None

    def test_empty_response_returns_none(self):
        assert _extract_workflow_json("") is None

    def test_invalid_json_returns_none(self):
        assert _extract_workflow_json("{not valid json") is None

    def test_invalid_json_in_code_block(self):
        assert _extract_workflow_json("```json\n{invalid\n```") is None


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_workflow
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateWorkflow:
    def test_valid_workflow_passes(self):
        errors = _validate_workflow(_valid_workflow())
        assert errors == []

    def test_missing_node_id(self):
        wf = {"nodes": [{"node_type": "ma", "label": "MA"}], "edges": []}
        errors = _validate_workflow(wf)
        assert any("missing" in e.lower() or "id" in e.lower() for e in errors)

    def test_unknown_node_type(self):
        wf = {
            "nodes": [{"id": "n1", "node_type": "this_does_not_exist", "label": "X"}],
            "edges": [],
        }
        errors = _validate_workflow(wf)
        assert any("unknown node_type" in e for e in errors)

    def test_edge_references_unknown_source(self):
        wf = _valid_workflow()
        wf["edges"].append({
            "id": "e_bad",
            "source": "n_ghost",
            "source_port": "series",
            "target": "n_ma",
            "target_port": "series",
        })
        errors = _validate_workflow(wf)
        assert any("unknown source" in e for e in errors)

    def test_edge_references_unknown_target(self):
        wf = _valid_workflow()
        wf["edges"].append({
            "id": "e_bad",
            "source": "n_data",
            "source_port": "series",
            "target": "n_ghost",
            "target_port": "series",
        })
        errors = _validate_workflow(wf)
        assert any("unknown target" in e for e in errors)

    def test_no_nodes(self):
        errors = _validate_workflow({"nodes": [], "edges": []})
        assert len(errors) > 0

    def test_valid_known_node_types_work(self):
        """All well-known node types should pass validation."""
        wf = {
            "nodes": [
                {"id": "n1", "node_type": "column_extract", "label": "close",
                 "position": {"x": 0, "y": 0}, "config": {"column": "close"}},
                {"id": "n2", "node_type": "ma", "label": "MA(5)",
                 "position": {"x": 260, "y": 0}, "config": {"window": 5}},
                {"id": "n3", "node_type": "rank_select", "label": "Top 10",
                 "position": {"x": 520, "y": 0}, "config": {"top_n": 10}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "source_port": "series",
                 "target": "n2", "target_port": "series"},
                {"id": "e2", "source": "n2", "source_port": "ma",
                 "target": "n3", "target_port": "factor"},
            ],
        }
        errors = _validate_workflow(wf)
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════════════
# get_node_catalog
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetNodeCatalog:
    def test_returns_non_empty_list(self):
        catalog = get_node_catalog()
        assert isinstance(catalog, list)
        assert len(catalog) > 0

    def test_each_entry_has_required_fields(self):
        catalog = get_node_catalog()
        for entry in catalog:
            assert "node_type" in entry
            assert "category" in entry
            assert "label" in entry
            assert "description" in entry
            assert isinstance(entry["inputs"], list)
            assert isinstance(entry["outputs"], list)

    def test_known_node_types_present(self):
        catalog = get_node_catalog()
        types = {e["node_type"] for e in catalog}
        assert "column_extract" in types
        assert "ma" in types
        assert "rank_select" in types
        assert "arithmetic" in types
