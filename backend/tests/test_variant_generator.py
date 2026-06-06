"""Tests for VariantGenerator — strategy variant generation."""

from src.services.variant_generator import VariantGenerator, _deep_set


class TestVariantGenerator:
    """Unit tests for variant generation logic."""

    def test_grid_empty_space(self):
        gen = VariantGenerator()
        base = {"top_n": 5}
        variants = gen.generate(base, {}, method="grid")
        assert len(variants) == 1
        assert variants[0] == base

    def test_grid_respects_max(self):
        gen = VariantGenerator()
        base = {"top_n": 5}
        space = {
            "top_n": [3, 5, 10, 20],
            "window": [10, 20, 30, 60],
        }
        variants = gen.generate(base, space, method="grid", max_variants=8)
        # Cartesian product is 16, but max_variants caps at 8
        assert 1 <= len(variants) <= 8

    def test_random_respects_max(self):
        gen = VariantGenerator()
        base = {"top_n": 5}
        space = {
            "top_n": [3, 5, 10, 20, 50],
            "window": [10, 20, 30, 60, 120],
        }
        variants = gen.generate(base, space, method="random", max_variants=10, seed=42)
        assert 1 <= len(variants) <= 10

    def test_variants_include_meta(self):
        gen = VariantGenerator()
        base = {"top_n": 5}
        space = {"top_n": [3, 5]}
        variants = gen.generate(base, space, method="grid", max_variants=4)
        for v in variants:
            assert "_variant_meta" in v
            assert "overrides" in v["_variant_meta"]
            assert v["_variant_meta"]["method"] == "grid"

    def test_base_not_mutated(self):
        gen = VariantGenerator()
        base = {"top_n": 5, "extra": {"deep": 10}}
        space = {"top_n": [3, 5, 10]}
        variants = gen.generate(base, space, method="grid", max_variants=3)
        # Original should be unchanged
        assert base["top_n"] == 5
        assert base["extra"]["deep"] == 10

    def test_deep_set(self):
        d = {"a": {"b": {"c": 1}}}
        _deep_set(d, "a.b.c", 42)
        assert d["a"]["b"]["c"] == 42

        _deep_set(d, "x.y.z", 99)
        assert d["x"]["y"]["z"] == 99

    def test_deterministic_with_seed(self):
        gen = VariantGenerator()
        base = {"top_n": 5}
        space = {"top_n": [3, 5, 10, 20, 50], "window": [10, 20, 30]}
        v1 = gen.generate(base, space, method="random", max_variants=5, seed=123)
        v2 = gen.generate(base, space, method="random", max_variants=5, seed=123)
        # Same seed should produce same variants
        assert len(v1) == len(v2)
        for a, b in zip(v1, v2):
            assert a["_variant_meta"]["overrides"] == b["_variant_meta"]["overrides"]
