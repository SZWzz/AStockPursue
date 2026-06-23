"""Test FactorKnowledgeBase registration and load for _by_source_version index."""

import tempfile
import os

from src.factors.mining.factor_kb import FactorKnowledgeBase
from src.factors.mining.expression_tree import ExpressionTree


def test_register_adds_to_source_version_index():
    """Registering a factor with data_source_version should populate _by_source_version."""
    kb = FactorKnowledgeBase()
    tree = ExpressionTree.from_formula("rank(close)")
    entry, ok = kb.register(
        tree,
        alpha_id="test_alpha_001",
        source="test",
        data_source_version="v2024-01-01",
    )
    assert ok
    assert "v2024-01-01" in kb._by_source_version
    assert "test_alpha_001" in kb._by_source_version["v2024-01-01"]


def test_load_populates_source_version_index():
    """Loading factors from a saved file should populate _by_source_version correctly."""
    kb1 = FactorKnowledgeBase()
    tree = ExpressionTree.from_formula("rank(close)")
    kb1.register(
        tree,
        alpha_id="alpha_x",
        source="test",
        data_source_version="v2024-06-01",
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        kb1.save(f.name)
        tmp_path = f.name

    try:
        kb2 = FactorKnowledgeBase.load(tmp_path)
        assert "v2024-06-01" in kb2._by_source_version
        assert "alpha_x" in kb2._by_source_version["v2024-06-01"]
    finally:
        os.unlink(tmp_path)
