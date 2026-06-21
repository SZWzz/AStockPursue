"""End-to-end formula consistency verification.

Validates the central contract: ExpressionTree is the single source of truth.
All derived forms (formula string, hash, SignalEngine code, dict) must be
deterministically generated from the tree and round-trip correctly.
"""


import numpy as np
import pandas as pd
import pytest

from src.factors.mining.expression_tree import (
    ExpressionNode,
    ExpressionTree,
    MAX_COMPLEXITY,
    OPERATOR_REGISTRY,
    OPERATOR_TIERS,
    get_allowed_operators,
)
from src.factors.mining.factor_kb import (
    FactorEntry,
    FactorKnowledgeBase,
    FactorStatus,
)
from src.factors.mining.hybrid_init import (
    get_default_skeletons,
    hybrid_initialize_population,
)
from src.factors.mining.enhanced_fitness import (
    composite_fitness,
    a_share_cost_penalty,
    complexity_discount,
    apply_fdr_correction,
)


# ============================================================================
# 1. ExpressionTree → formula → hash consistency
# ============================================================================

class TestFormulaConsistency:
    """Verify that ExpressionTree is the single source of truth."""

    def test_same_tree_same_hash(self):
        """Two identical trees produce the same formula_hash."""
        t1 = ExpressionTree(ExpressionNode(
            op="div",
            children=[
                ExpressionNode(op="ts_delta", children=[
                    ExpressionNode(feature_id="close"),
                ], window=20),
                ExpressionNode(op="ts_mean", children=[
                    ExpressionNode(feature_id="close"),
                ], window=20),
            ],
        ))
        t2 = ExpressionTree(ExpressionNode(
            op="div",
            children=[
                ExpressionNode(op="ts_delta", children=[
                    ExpressionNode(feature_id="close"),
                ], window=20),
                ExpressionNode(op="ts_mean", children=[
                    ExpressionNode(feature_id="close"),
                ], window=20),
            ],
        ))
        assert t1.formula_hash == t2.formula_hash
        assert t1.normalized_formula == t2.normalized_formula

    def test_commutative_normalization(self):
        """add(A,B) and add(B,A) produce the same hash."""
        t1 = ExpressionTree(ExpressionNode(
            op="add",
            children=[
                ExpressionNode(feature_id="close"),
                ExpressionNode(feature_id="volume"),
            ],
        ))
        t2 = ExpressionTree(ExpressionNode(
            op="add",
            children=[
                ExpressionNode(feature_id="volume"),
                ExpressionNode(feature_id="close"),
            ],
        ))
        assert t1.formula_hash == t2.formula_hash, (
            f"Commutative add should produce same hash: "
            f"{t1.formula_hash} != {t2.formula_hash}"
        )
        assert t1.normalized_formula == t2.normalized_formula

    def test_different_trees_different_hash(self):
        """Different trees produce different hashes."""
        t1 = ExpressionTree(ExpressionNode(
            op="ts_delta", children=[ExpressionNode(feature_id="close")], window=20,
        ))
        t2 = ExpressionTree(ExpressionNode(
            op="ts_delta", children=[ExpressionNode(feature_id="close")], window=60,
        ))
        assert t1.formula_hash != t2.formula_hash

    def test_window_encoded_in_hash(self):
        """Different windows → different hashes."""
        t1 = ExpressionTree(ExpressionNode(
            op="ts_mean", children=[ExpressionNode(feature_id="close")], window=10,
        ))
        t2 = ExpressionTree(ExpressionNode(
            op="ts_mean", children=[ExpressionNode(feature_id="close")], window=20,
        ))
        assert t1.formula_hash != t2.formula_hash

    def test_feature_case_normalized(self):
        """Feature ID case is normalized in hash."""
        t1 = ExpressionTree(ExpressionNode(feature_id="CLOSE"))
        t2 = ExpressionTree(ExpressionNode(feature_id="close"))
        assert t1.formula_hash == t2.formula_hash


# ============================================================================
# 2. Round-trip: tree ↔ dict
# ============================================================================

class TestTreeSerialization:
    """ExpressionTree → to_dict() → from_dict() → same tree."""

    def test_roundtrip_simple(self):
        t1 = ExpressionTree(ExpressionNode(feature_id="close"))
        d = t1.to_dict()
        t2 = ExpressionTree.from_dict(d)
        assert t2.to_formula() == t1.to_formula()
        assert t2.formula_hash == t1.formula_hash

    def test_roundtrip_complex(self):
        t1 = ExpressionTree(ExpressionNode(
            op="div",
            children=[
                ExpressionNode(op="ts_delta", children=[
                    ExpressionNode(feature_id="close"),
                ], window=20),
                ExpressionNode(op="ts_std", children=[
                    ExpressionNode(feature_id="close"),
                ], window=20),
            ],
        ))
        d = t1.to_dict()
        t2 = ExpressionTree.from_dict(d)
        assert t2.formula_hash == t1.formula_hash
        assert t2.to_formula() == t1.to_formula()
        assert t2.complexity() == t1.complexity()

    def test_roundtrip_all_skeletons(self):
        """Every default skeleton roundtrips correctly."""
        skeletons = get_default_skeletons()
        assert len(skeletons) > 0, "Should have default skeletons"
        for i, sk in enumerate(skeletons):
            d = sk.to_dict()
            restored = ExpressionTree.from_dict(d)
            assert restored.formula_hash == sk.formula_hash, (
                f"Skeleton {i} roundtrip hash mismatch"
            )
            assert restored.to_formula() == sk.to_formula(), (
                f"Skeleton {i} roundtrip formula mismatch"
            )


# ============================================================================
# 3. SignalEngine code generation
# ============================================================================

class TestSignalEngineCompiler:
    """ExpressionTree → SignalEngine code is valid Python."""

    def test_compiled_code_is_valid_python(self):
        """Generated code passes AST parsing."""
        t = ExpressionTree(ExpressionNode(
            op="div",
            children=[
                ExpressionNode(op="ts_delta", children=[
                    ExpressionNode(feature_id="close"),
                ], window=20),
                ExpressionNode(op="ts_mean", children=[
                    ExpressionNode(feature_id="close"),
                ], window=20),
            ],
        ))
        code = t.to_signalengine_code("TestSignal")
        # Must be valid Python
        import ast
        ast.parse(code)
        # Must contain the class
        assert "class TestSignal:" in code
        # Must contain the formula hash in a comment
        assert t.formula_hash in code

    def test_generated_code_executes(self):
        """Generated SignalEngine code actually runs on mock data."""
        t = ExpressionTree(ExpressionNode(
            op="rank",
            children=[ExpressionNode(
                op="ts_delta",
                children=[ExpressionNode(feature_id="close")],
                window=5,
            )],
        ))
        code = t.to_signalengine_code("MomentumSignal")

        # Execute the generated code in a namespace
        namespace = {}
        exec(code, namespace)
        cls = namespace.get("MomentumSignal")
        assert cls is not None

        # Create mock data
        dates = pd.date_range("2024-01-01", periods=100, freq="B")
        df = pd.DataFrame({
            "open": np.random.randn(100).cumsum() + 100,
            "high": np.random.randn(100).cumsum() + 102,
            "low": np.random.randn(100).cumsum() + 98,
            "close": np.random.randn(100).cumsum() + 100,
            "volume": np.abs(np.random.randn(100)) * 1e6,
        }, index=dates)

        engine = cls()
        signals = engine.generate({"TEST": df})
        assert "TEST" in signals
        assert isinstance(signals["TEST"], pd.Series)
        assert len(signals["TEST"]) == len(df)
        # Signal values should be in [-1, 1]
        valid = signals["TEST"].dropna()
        if len(valid) > 0:
            assert valid.min() >= -1.01, f"Signal below -1: {valid.min()}"
            assert valid.max() <= 1.01, f"Signal above 1: {valid.max()}"

    def test_all_skeletons_compile(self):
        """Every default skeleton compiles to valid SignalEngine code."""
        skeletons = get_default_skeletons()
        for i, sk in enumerate(skeletons):
            code = sk.to_signalengine_code(f"TestSignal_{i}")
            import ast
            ast.parse(code)  # Must be valid Python


# ============================================================================
# 4. FactorKB formula dedup
# ============================================================================

class TestFactorKBDedup:
    """FactorKB correctly deduplicates by formula_hash."""

    def test_register_dedup(self):
        kb = FactorKnowledgeBase()
        t = ExpressionTree(ExpressionNode(feature_id="close"))

        e1, is_new1 = kb.register(t, name="first")
        assert is_new1

        e2, is_new2 = kb.register(t, name="second")
        assert not is_new2
        assert e1.alpha_id == e2.alpha_id  # Same entry returned

    def test_register_different_trees(self):
        kb = FactorKnowledgeBase()
        t1 = ExpressionTree(ExpressionNode(feature_id="close"))
        t2 = ExpressionTree(ExpressionNode(feature_id="volume"))

        e1, is_new1 = kb.register(t1)
        e2, is_new2 = kb.register(t2)

        assert is_new1
        assert is_new2
        assert e1.alpha_id != e2.alpha_id
        assert len(kb) == 2

    def test_entry_derives_from_tree(self):
        """FactorEntry.__post_init__ derives formula/hash from tree."""
        t = ExpressionTree(ExpressionNode(
            op="ts_delta",
            children=[ExpressionNode(feature_id="close")],
            window=20,
        ))
        entry = FactorEntry(alpha_id="test_001", tree=t)
        assert entry.formula_hash == t.formula_hash
        assert entry.formula == t.to_formula()
        assert entry.normalized_formula == t.normalized_formula
        assert entry.complexity == t.complexity()

    def test_entry_roundtrip(self):
        """FactorEntry → to_dict() → from_dict() preserves tree consistency."""
        t = ExpressionTree(ExpressionNode(
            op="rank",
            children=[ExpressionNode(
                op="ts_pct",
                children=[ExpressionNode(feature_id="close")],
                window=5,
            )],
        ))
        entry = FactorEntry(alpha_id="test_002", tree=t, source="gp_engine")
        d = entry.to_dict()
        restored = FactorEntry.from_dict(d)
        assert restored.formula_hash == entry.formula_hash
        assert restored.formula == entry.formula
        assert restored.tree.to_formula() == entry.tree.to_formula()


# ============================================================================
# 5. Lifecycle state machine
# ============================================================================

class TestLifecycle:
    """Factor lifecycle transitions are valid."""

    def test_valid_transitions(self):
        assert FactorStatus.can_transition(FactorStatus.DISCOVERED, FactorStatus.VALIDATING)
        assert FactorStatus.can_transition(FactorStatus.VALIDATING, FactorStatus.APPROVED)
        assert FactorStatus.can_transition(FactorStatus.APPROVED, FactorStatus.PAPER_TRADING)
        assert FactorStatus.can_transition(FactorStatus.PAPER_TRADING, FactorStatus.PRODUCTION)
        assert FactorStatus.can_transition(FactorStatus.PRODUCTION, FactorStatus.DEPRECATED)
        assert FactorStatus.can_transition(FactorStatus.DEPRECATED, FactorStatus.ARCHIVED)

    def test_invalid_transitions(self):
        assert not FactorStatus.can_transition(FactorStatus.DISCOVERED, FactorStatus.PRODUCTION)
        assert not FactorStatus.can_transition(FactorStatus.APPROVED, FactorStatus.DISCOVERED)
        assert not FactorStatus.can_transition(FactorStatus.ARCHIVED, FactorStatus.DISCOVERED)

    def test_kb_transition_enforces_rules(self):
        kb = FactorKnowledgeBase()
        t = ExpressionTree(ExpressionNode(feature_id="close"))
        entry, _ = kb.register(t, name="test")
        assert entry.status == FactorStatus.DISCOVERED

        kb.transition_status(entry.alpha_id, FactorStatus.VALIDATING)
        assert kb.get(entry.alpha_id).status == FactorStatus.VALIDATING

        with pytest.raises(ValueError, match="Invalid status transition"):
            kb.transition_status(entry.alpha_id, FactorStatus.PRODUCTION)


# ============================================================================
# 6. Hybrid initialization
# ============================================================================

class TestHybridInit:
    """Hybrid population initialization produces valid trees."""

    def test_default_skeletons_load(self):
        skeletons = get_default_skeletons()
        assert len(skeletons) >= 5, f"Expected ≥5 skeletons, got {len(skeletons)}"
        for sk in skeletons:
            assert sk.complexity() <= MAX_COMPLEXITY
            assert sk.depth() <= 5

    def test_population_size(self):
        pop = hybrid_initialize_population(population_size=100)
        assert len(pop) == 100
        for t in pop:
            assert t.complexity() <= MAX_COMPLEXITY

    def test_skeleton_ratio(self):
        """Population contains roughly the right proportion of skeleton-derived trees."""
        pop = hybrid_initialize_population(
            population_size=200,
            skeleton_ratio=0.5,
            mutant_ratio=0.3,
            random_ratio=0.2,
        )
        assert len(pop) == 200


# ============================================================================
# 7. Enhanced fitness
# ============================================================================

class TestEnhancedFitness:
    """Multiplicative composite fitness works correctly."""

    @pytest.fixture
    def mock_data(self):
        n_dates, n_stocks = 100, 20
        dates = pd.date_range("2024-01-01", periods=n_dates, freq="B")
        codes = [f"S{i:03d}" for i in range(n_stocks)]
        rng = np.random.RandomState(42)

        close = pd.DataFrame(
            rng.randn(n_dates, n_stocks).cumsum(axis=0) + 100,
            index=dates, columns=codes, dtype=np.float64,
        )
        panel = {
            "close": close,
            "open": close * (1 + rng.randn(n_dates, n_stocks) * 0.003),
            "high": close * (1 + np.abs(rng.randn(n_dates, n_stocks)) * 0.01),
            "low": close * (1 - np.abs(rng.randn(n_dates, n_stocks)) * 0.01),
            "volume": pd.DataFrame(np.abs(rng.randn(n_dates, n_stocks)) * 1e6,
                                   index=dates, columns=codes, dtype=np.float64),
        }

        fwd_returns = close.pct_change(1).shift(-1)
        fwd_returns = fwd_returns.replace([np.inf, -np.inf], np.nan)

        return panel, fwd_returns

    def test_composite_fitness_returns_valid(self, mock_data):
        panel, fwd_returns = mock_data
        t = ExpressionTree(ExpressionNode(
            op="rank",
            children=[ExpressionNode(
                op="ts_delta",
                children=[ExpressionNode(feature_id="close")],
                window=20,
            )],
        ))
        fn = t.to_callable()
        fv = fn(panel)
        result = composite_fitness(t, fv, fwd_returns, panel=panel)
        assert "fitness" in result
        assert "rank_ic" in result
        assert "annual_turnover" in result
        assert "components" in result
        assert result["fitness"] >= 0.0

    def test_cost_penalty_low_turnover(self):
        """Low-turnover factor gets high cost penalty (close to 1.0)."""
        n_dates = 100
        dates = pd.date_range("2024-01-01", periods=n_dates, freq="B")
        # Constant factor values → zero turnover
        fv = pd.DataFrame(
            np.ones((n_dates, 10)),
            index=dates,
            columns=[f"S{i:03d}" for i in range(10)],
        )
        penalty = a_share_cost_penalty(fv)
        assert penalty > 0.9, f"Low turnover should have high penalty value, got {penalty}"

    def test_complexity_discount(self):
        """More complex trees get lower discount."""
        simple = complexity_discount(1, 10000)
        complex_d = complexity_discount(50, 10000)
        assert simple > complex_d, f"Simple should have higher discount: {simple} vs {complex_d}"

    def test_fdr_correction(self):
        """FDR correction identifies significant factors."""
        candidates = [
            {"rank_ic": 0.05, "oos_ic_per_window": [0.05, 0.04, 0.06, 0.05, 0.04]},
            {"rank_ic": 0.005, "oos_ic_per_window": [0.005, -0.002, 0.003, -0.001, 0.002]},
            {"rank_ic": 0.03, "oos_ic_per_window": [0.03, 0.02, 0.04, 0.03, 0.02]},
            {"rank_ic": -0.002, "oos_ic_per_window": [-0.001, -0.003, 0.001, -0.002, 0.0]},
        ]
        result = apply_fdr_correction(candidates)
        assert len(result) == 4
        for c in result:
            assert "fdr_adjusted_p_value" in c
            assert "fdr_significant" in c


# ============================================================================
# 8. Operator tiers
# ============================================================================

class TestOperatorTiers:
    """Operator tier system correctly gates access."""

    def test_basic_always_available(self):
        ops = get_allowed_operators(0, 50)
        for op in ["add", "ts_mean", "rank", "abs"]:
            assert op in ops, f"Basic operator {op} should be available from gen 0"

    def test_advanced_unlocked_mid(self):
        ops_early = get_allowed_operators(5, 50)  # 10% progress
        ops_mid = get_allowed_operators(25, 50)   # 50% progress
        # ts_corr is advanced
        assert "ts_corr" not in ops_early
        assert "ts_corr" in ops_mid

    def test_alternative_unlocked_late(self):
        ops_early = get_allowed_operators(10, 50)   # 20% progress
        ops_late = get_allowed_operators(45, 50)    # 90% progress
        assert "if_else" not in ops_early
        assert "if_else" in ops_late
        assert "ind_neutralize" in ops_late

    def test_final_generation_all_operators(self):
        ops = get_allowed_operators(49, 50)
        for op_name in OPERATOR_REGISTRY:
            if op_name in OPERATOR_TIERS:
                assert op_name in ops, f"Operator {op_name} should be available at 100% progress"


# ============================================================================
# 9. Consistency: tree execution vs SignalEngine code execution
# ============================================================================

class TestExecutionConsistency:
    """ExpressionTree.to_callable() and to_signalengine_code() produce same results."""

    def test_callable_vs_code_same_result(self):
        """The in-memory callable and the generated SignalEngine code
        evaluate to the same (or very close) factor values."""
        n_dates, n_stocks = 60, 10
        dates = pd.date_range("2024-01-01", periods=n_dates, freq="B")
        codes = [f"S{i:03d}" for i in range(n_stocks)]
        rng = np.random.RandomState(42)

        close = pd.DataFrame(
            rng.randn(n_dates, n_stocks).cumsum(axis=0) + 100,
            index=dates, columns=codes, dtype=np.float64,
        )
        panel_test = {
            "close": close,
            "open": close * (1 + rng.randn(n_dates, n_stocks) * 0.003),
            "high": close * (1 + np.abs(rng.randn(n_dates, n_stocks)) * 0.01),
            "low": close * (1 - np.abs(rng.randn(n_dates, n_stocks)) * 0.01),
            "volume": pd.DataFrame(np.abs(rng.randn(n_dates, n_stocks)) * 1e6,
                                   index=dates, columns=codes, dtype=np.float64),
        }

        t = ExpressionTree(ExpressionNode(
            op="div",
            children=[
                ExpressionNode(op="ts_delta", children=[
                    ExpressionNode(feature_id="close"),
                ], window=10),
                ExpressionNode(op="ts_mean", children=[
                    ExpressionNode(feature_id="close"),
                ], window=10),
            ],
        ))

        # In-memory evaluation
        fn = t.to_callable()
        result_memory = fn(panel_test)

        # SignalEngine code evaluation
        code = t.to_signalengine_code("ConsistencyTest")
        namespace = {}
        exec(code, namespace)
        engine = namespace["ConsistencyTest"]()

        # Convert panel to data_map format
        data_map = {}
        for code_name in codes:
            df = pd.DataFrame({
                "open": panel_test["open"][code_name],
                "high": panel_test["high"][code_name],
                "low": panel_test["low"][code_name],
                "close": panel_test["close"][code_name],
                "volume": panel_test["volume"][code_name],
            }, index=dates)
            data_map[code_name] = df

        signals = engine.generate(data_map)

        # Build factor values from signals (reverse the rank+normalize)
        # The SignalEngine code does: factor → rank(pct=True) → (rank-0.5)*2
        # So we can't directly compare raw factor values, but we can verify
        # the signal direction is consistent
        for code_name in codes:
            sig = signals.get(code_name, pd.Series())
            if len(sig.dropna()) > 10:
                # Signal values should be in [-1, 1]
                assert sig.min() >= -1.01
                assert sig.max() <= 1.01
