"""gRPC FactorService — factor computation and GP evolution.

Wraps the factor mining domain modules (ExpressionTree, GPEvolution,
FactorKnowledgeBase) behind the protobuf contract defined in factor.proto.
"""
from __future__ import annotations

import logging

import grpc
import pandas as pd

from src.gen import factor_pb2, factor_pb2_grpc

logger = logging.getLogger(__name__)


class FactorServiceServicer(factor_pb2_grpc.FactorServiceServicer):
    """gRPC implementation of FactorService."""

    def ComputeFactor(self, request, context):
        """Compute factor values for given symbols and date range."""
        formula = request.formula
        symbols = list(request.symbols) if request.symbols else []
        start_date = request.start_date
        end_date = request.end_date

        if not formula:
            return factor_pb2.FactorResponse(
                values={}, error="formula is required"
            )
        if not symbols:
            return factor_pb2.FactorResponse(
                values={}, error="at least one symbol required"
            )

        try:
            from src.factors.mining.expression_tree import ExpressionTree

            tree = ExpressionTree.from_formula(formula)
            compute_fn = tree.to_callable()

            # Load data for each symbol via DataStore (resilient to missing
            # cache modules or DB connections — falls back to empty panel)
            data_map: dict[str, pd.DataFrame] = {}
            try:
                from backtest.data_store import get_data_store

                store = get_data_store()
                for sym in symbols:
                    df = store.get_ohlcv(sym, start_date, end_date)
                    if df is not None and not df.empty:
                        data_map[sym] = df
            except (ImportError, ModuleNotFoundError, RuntimeError) as e:
                logger.warning("DataStore unavailable for factor compute: %s", e)
            except Exception as e:
                logger.warning("DataStore error for factor compute: %s", e)

            if not data_map:
                return factor_pb2.FactorResponse(
                    values={}, error="no data available for requested symbols"
                )

            # Build panel from per-symbol data: feature_name -> DataFrame(symbols)
            panel: dict[str, pd.DataFrame] = {}
            ohlcv_cols = ["open", "high", "low", "close", "volume"]
            for col in ohlcv_cols:
                col_data = {}
                for sym, df in data_map.items():
                    if col in df.columns:
                        col_data[sym] = df[col]
                if col_data:
                    panel[col] = pd.DataFrame(col_data)

            result = compute_fn(panel)
            # Convert result to protobuf values (last row)
            values: dict[str, float] = {}
            if hasattr(result, "iloc") and hasattr(result, "columns"):
                last_row = result.iloc[-1]
                for sym in result.columns:
                    val = last_row[sym]
                    if pd.notna(val):
                        values[sym] = float(val)
            elif isinstance(result, pd.Series):
                for sym in result.index:
                    val = result[sym]
                    if pd.notna(val):
                        values[sym] = float(val)

            return factor_pb2.FactorResponse(values=values, error="")

        except ValueError as e:
            logger.warning("Factor formula parse error: %s", e)
            return factor_pb2.FactorResponse(values={}, error=str(e))
        except Exception as e:
            logger.exception("Factor computation failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
            return factor_pb2.FactorResponse(values={}, error=str(e))

    def StartGPMining(self, request, context):
        """Run GP evolution, streaming results per generation."""
        pool = request.pool if request.pool else "a_share"
        generations = request.generations if request.generations else 20
        population_size = request.population_size if request.population_size else 200
        fitness_metric = request.fitness_metric if request.fitness_metric else "composite"

        try:
            from src.factors.mining.gp_engine import GPEvolution, GPEvolutionConfig

            # Map pool string to default universe (empty means use GP engine's default)
            universe: list[str] = []
            if pool == "a_share":
                pass  # Use GPEvolution defaults
            elif pool == "crypto":
                pass  # Use GPEvolution defaults
            else:
                logger.warning("Unknown pool '%s', using defaults", pool)

            config = GPEvolutionConfig(
                generations=generations,
                population_size=population_size,
                fitness_metric=fitness_metric,
                universe=universe,
                use_tiered_operators=True,
                use_hybrid_init=True,
                use_kb=True,
            )
            gp = GPEvolution(config=config)
            gp_result = gp.run()

            for gen_idx, gen_data in enumerate(gp_result.generation_history):
                best = gp_result.best_individuals[gen_idx] if gen_idx < len(gp_result.best_individuals) else None
                yield factor_pb2.GPResult(
                    formula=best.formula if best else "",
                    ic=best.test_ic if best and hasattr(best, "test_ic") else 0.0,
                    sharpe=getattr(best, "sharpe", 0.0) if best else 0.0,
                    generation=gen_idx + 1,
                )

        except Exception as e:
            logger.exception("GP mining failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
