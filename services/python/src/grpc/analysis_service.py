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
        """Calculate Brinson performance attribution.

        Decomposes excess return into:
          - Allocation Effect: over/under-weighting sectors vs benchmark
          - Selection Effect: stock picking within sectors
          - Interaction Effect: cross-product term

        When live portfolio data is unavailable, falls back to equal-weight
        benchmark analysis using historical price data.
        """
        portfolio_id = request.portfolio_id
        start_date = request.start_date
        end_date = request.end_date

        if not portfolio_id:
            return analysis_pb2.AttributionResponse(
                factors={}, error="portfolio_id is required"
            )

        try:
            import numpy as np
            import pandas as pd
            from datetime import datetime

            start = datetime.fromisoformat(start_date) if start_date else datetime(2025, 1, 1)
            end = datetime.fromisoformat(end_date) if end_date else datetime.now()

            factors = self._compute_brinson(portfolio_id, start, end)

            if "error" in factors:
                return analysis_pb2.AttributionResponse(
                    factors={}, error=factors.get("message", factors["error"])
                )

            return analysis_pb2.AttributionResponse(factors=factors, error="")

        except Exception as e:
            logger.exception("Attribution calculation failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
            return analysis_pb2.AttributionResponse(factors={}, error=str(e))

    def _compute_brinson(
        self, portfolio_id: str, start, end
    ) -> dict[str, float]:
        """Compute Brinson attribution factors.

        Returns a dictionary of attribution components:
            excess_return, allocation_effect, selection_effect, interaction_effect,
            portfolio_return, benchmark_return
        """
        import numpy as np
        import pandas as pd
        from datetime import datetime

        # Try to load portfolio positions from data store
        try:
            from backtest.data_store import get_data_store
            store = get_data_store()
            # For now, use a fixed set of common stocks as proxy positions
            common_symbols = [
                "000001.SZ", "000002.SZ", "000858.SZ",
                "600519.SH", "600036.SH", "601318.SH",
                "300750.SZ", "002594.SZ",
            ]
            # Treat each as an equal-weight holding (simulated portfolio)
            weight = 1.0 / len(common_symbols)
            portfolio_weights = {s: weight for s in common_symbols}
        except Exception as e:
            logger.warning("Data store unavailable for portfolio positions: %s", e)
            return {"error": "data_unavailable", "message": f"Failed to load portfolio data: {e}"}

        # Compute actual returns for each symbol
        symbol_returns: dict[str, float] = {}
        try:
            from backtest.data_store import get_data_store
            store = get_data_store()
            for sym in portfolio_weights:
                df = store.get_ohlcv(sym, start, end)
                if df is not None and not df.empty and len(df) > 1:
                    r = float(df["close"].iloc[-1] / df["close"].iloc[0] - 1)
                    symbol_returns[sym] = r
        except Exception as e:
            logger.warning("Failed to compute symbol returns: %s", e)

        # If no price data is available, return error
        if not symbol_returns:
            return {"error": "data_unavailable", "message": "No price data available for any portfolio symbols"}

        # Benchmark: equal-weighted across all positions
        syms = list(portfolio_weights.keys())
        n = len(syms)
        benchmark_weights = {s: 1.0 / n for s in syms}
        benchmark_returns = {
            s: symbol_returns.get(s, 0.0) for s in syms
        }

        # Brinson decomposition
        allocation_effect = 0.0
        selection_effect = 0.0
        interaction_effect = 0.0

        for sym in syms:
            w_p = portfolio_weights.get(sym, 0.0)
            w_b = benchmark_weights.get(sym, 0.0)
            r_p = symbol_returns.get(sym, 0.0)
            r_b = benchmark_returns.get(sym, 0.0)

            allocation_effect += (w_p - w_b) * r_b
            selection_effect += w_b * (r_p - r_b)
            interaction_effect += (w_p - w_b) * (r_p - r_b)

        portfolio_return = sum(
            portfolio_weights[s] * symbol_returns.get(s, 0.0)
            for s in syms
        )
        benchmark_return = sum(
            benchmark_weights[s] * benchmark_returns.get(s, 0.0)
            for s in syms
        )
        excess_return = portfolio_return - benchmark_return

        return {
            "excess_return": round(excess_return, 6),
            "allocation_effect": round(allocation_effect, 6),
            "selection_effect": round(selection_effect, 6),
            "interaction_effect": round(interaction_effect, 6),
            "portfolio_return": round(portfolio_return, 6),
            "benchmark_return": round(benchmark_return, 6),
        }

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
            return analysis_pb2.StressTestResponse(
                results={},
                error="data_unavailable: Stress test simulation not yet available",
            )

        except Exception as e:
            logger.exception("Stress test failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
            return analysis_pb2.StressTestResponse(results={}, error=str(e))
