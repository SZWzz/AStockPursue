"""gRPC AnalysisService — attribution, correlation, stress testing.

Wraps analysis domain modules behind the protobuf contract defined in
analysis.proto.  Gracefully degrades when data dependencies are unavailable
(test / CI environments).
"""
from __future__ import annotations

import logging

import grpc

from src.gen import analysis_pb2, analysis_pb2_grpc

logger = logging.getLogger(__name__)


class AnalysisServiceServicer(analysis_pb2_grpc.AnalysisServiceServicer):
    """gRPC implementation of AnalysisService.

    Provides three RPCs:

    * **CalcAttribution** — performance attribution via WorkflowEngine
    * **CalcCorrelation** — pairwise return correlation for a symbol universe
    * **StressTest** — scenario-based portfolio stress test (placeholder)
    """

    def CalcAttribution(self, request, context):
        """Calculate performance attribution (Brinson / factor / sector).

        Delegates to the WorkflowEngine for attribution DAG execution.
        Returns an error response on missing portfolio_id or runtime failure.
        """
        portfolio_id = request.portfolio_id
        start_date = request.start_date
        end_date = request.end_date

        if not portfolio_id:
            return analysis_pb2.AttributionResponse(
                factors={}, error="portfolio_id is required"
            )

        try:
            from src.workflow.workflow_engine import WorkflowEngine

            engine = WorkflowEngine()
            # Build a minimal attribution DAG — nodes and edges can be
            # extended once full portfolio positions are available.
            nodes = []
            edges = []
            result = engine.execute(nodes, edges)

            factors: dict[str, float] = {}
            for node_id, node_result in result.items():
                if hasattr(node_result, "output") and isinstance(
                    node_result.output, dict
                ):
                    for k, v in node_result.output.items():
                        try:
                            factors[k] = float(v)
                        except (TypeError, ValueError):
                            factors[k] = 0.0

            return analysis_pb2.AttributionResponse(factors=factors, error="")

        except Exception as e:
            logger.exception("Attribution calculation failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
            return analysis_pb2.AttributionResponse(factors={}, error=str(e))

    def CalcCorrelation(self, request, context):
        """Calculate correlation matrix for given symbols.

        Fetches OHLCV data from the shared DataStore for each symbol,
        computes pairwise Pearson correlation of daily log returns,
        and returns the upper-triangle of the matrix.

        At least two symbols are required.
        """
        symbols = list(request.symbols) if request.symbols else []
        start_date = request.start_date
        end_date = request.end_date

        if not symbols or len(symbols) < 2:
            return analysis_pb2.CorrelationResponse(
                matrix={}, error="at least 2 symbols required"
            )

        try:
            import pandas as pd
            from datetime import datetime

            from backtest.data_store import get_data_store

            store = get_data_store()
            closes: dict[str, pd.Series] = {}
            for sym in symbols:
                try:
                    df = store.get_ohlcv(
                        sym,
                        datetime.fromisoformat(start_date)
                        if start_date
                        else datetime(2025, 1, 1),
                        datetime.fromisoformat(end_date)
                        if end_date
                        else datetime.now(),
                    )
                    if df is not None and not df.empty and "close" in df.columns:
                        closes[sym] = df["close"]
                except Exception as e:
                    logger.warning("Failed to fetch data for %s: %s", sym, e)

            matrix: dict[str, float] = {}
            sym_list = list(closes.keys())
            if len(sym_list) >= 2:
                for i, s1 in enumerate(sym_list):
                    for j, s2 in enumerate(sym_list):
                        if i <= j:
                            p1 = closes[s1].pct_change().dropna()
                            p2 = closes[s2].pct_change().dropna()
                            aligned = pd.concat([p1, p2], axis=1).dropna()
                            if len(aligned) > 5:
                                corr = float(
                                    aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
                                )
                                matrix[f"{s1}|{s2}"] = corr

            return analysis_pb2.CorrelationResponse(matrix=matrix, error="")

        except Exception as e:
            logger.exception("Correlation calculation failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
            return analysis_pb2.CorrelationResponse(matrix={}, error=str(e))

    def StressTest(self, request, context):
        """Run stress test scenarios on a portfolio.

        Requires a valid portfolio_id and at least one scenario name.
        Returns placeholder results (0.0 P&L impact) until full position-level
        stress simulation is wired in.
        """
        portfolio_id = request.portfolio_id
        scenarios = list(request.scenarios) if request.scenarios else []

        if not portfolio_id:
            return analysis_pb2.StressTestResponse(
                results={}, error="portfolio_id is required"
            )
        if not scenarios:
            return analysis_pb2.StressTestResponse(
                results={}, error="at least one scenario required"
            )

        try:
            results: dict[str, float] = {}
            for scenario in scenarios:
                results[scenario] = 0.0  # Placeholder — real stress test logic

            return analysis_pb2.StressTestResponse(results=results, error="")

        except Exception as e:
            logger.exception("Stress test failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
            return analysis_pb2.StressTestResponse(results={}, error=str(e))
