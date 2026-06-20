"""gRPC server for Go core ↔ Python research layer integration.

Implements SignalService (and future services) so Go's trading pipeline
can call Python for signal generation, factor computation, and AI decisions.

Usage:
    python -m src.grpc.server          # start on default port 8902
    python -m src.grpc.server --port 8903
"""

from __future__ import annotations

import argparse
import logging
from concurrent import futures

import grpc
import numpy as np
import pandas as pd

from src.gen import data_pb2_grpc, factor_pb2_grpc, signal_pb2, signal_pb2_grpc
from src.grpc.data_service import DataServiceServicer
from src.grpc.factor_service import FactorServiceServicer

logger = logging.getLogger(__name__)


class SignalServiceServicer(signal_pb2_grpc.SignalServiceServicer):
    """gRPC implementation of the SignalService.

    Receives bar data from Go, runs Python signal engine, returns target weights.
    Supports a pluggable strategy via ``set_strategy()``.
    """

    def __init__(self):
        self._strategy = None  # Will be set via set_strategy()

    def set_strategy(self, strategy_module):
        """Set the signal engine module or instance to use for GenerateSignals."""
        self._strategy = strategy_module

    def GenerateSignals(self, request, context):
        """Handle GenerateSignals gRPC call from Go.

        Converts protobuf bars → pandas DataFrame → runs strategy → returns weights.
        """
        strategy_name = request.strategy_name if request.strategy_name else "default"
        mode = request.mode if request.mode else "batch"

        logger.info(
            "GenerateSignals: strategy=%s mode=%s bars=%d",
            strategy_name, mode, len(request.bars),
        )

        # Convert protobuf bars to per-symbol pandas DataFrames
        data_map = self._bars_to_dataframe(request.bars)

        if not data_map:
            return signal_pb2.SignalResponse(
                weights={},
                error="no valid bars received",
            )

        # Generate weights
        try:
            weights = self._generate_weights(data_map, strategy_name, request.params)
        except Exception as exc:
            logger.exception("Signal generation failed")
            return signal_pb2.SignalResponse(
                weights={},
                error=str(exc),
            )

        return signal_pb2.SignalResponse(weights=weights)

    def _bars_to_dataframe(
        self, bars
    ) -> dict[str, pd.DataFrame]:
        """Convert repeated protobuf Bar messages to per-symbol DataFrames."""
        data: dict[str, list[dict]] = {}
        for bar in bars:
            ts = pd.Timestamp(bar.timestamp, unit="ms")
            row = {
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            if bar.symbol not in data:
                data[bar.symbol] = []
            data[bar.symbol].append((ts, row))

        result = {}
        for symbol, rows in data.items():
            index, values = zip(*rows)
            df = pd.DataFrame(values, index=pd.DatetimeIndex(index))
            df.sort_index(inplace=True)
            result[symbol] = df
        return result

    def _generate_weights(
        self,
        data_map: dict[str, pd.DataFrame],
        strategy_name: str,
        params: dict[str, str],
    ) -> dict[str, float]:
        """Run strategy to produce target weights.

        If no strategy is set, returns equal-weighted portfolio as default.
        """
        # If a custom strategy is registered, use it
        if self._strategy is not None:
            try:
                engine = self._strategy.SignalEngine()
                signals = engine.generate(data_map)
                return self._signals_to_weights(signals)
            except Exception:
                logger.warning("Custom strategy failed, falling back to equal-weight")

        # Default: equal-weighted portfolio
        symbols = list(data_map.keys())
        if not symbols:
            return {}

        weight = 1.0 / len(symbols)
        return {sym: weight for sym in symbols}

    def _signals_to_weights(self, signals: dict) -> dict[str, float]:
        """Convert raw signal series to target weights dict."""
        weights = {}
        for code, series in signals.items():
            if hasattr(series, "iloc") and len(series) > 0:
                val = float(series.iloc[-1])
                if not np.isnan(val):
                    weights[code] = val
            else:
                val = float(series)
                if not np.isnan(val):
                    weights[code] = val
        return weights


def serve(port: int = 8902, max_workers: int = 10) -> grpc.Server:
    """Start the gRPC server and return it (non-blocking in caller)."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))

    signal_servicer = SignalServiceServicer()
    signal_pb2_grpc.add_SignalServiceServicer_to_server(signal_servicer, server)

    data_servicer = DataServiceServicer()
    data_pb2_grpc.add_DataServiceServicer_to_server(data_servicer, server)

    factor_servicer = FactorServiceServicer()
    factor_pb2_grpc.add_FactorServiceServicer_to_server(factor_servicer, server)

    server.add_insecure_port(f"[::]:{port}")
    logger.info("gRPC server (SignalService + DataService + FactorService) listening on port %d", port)

    return server, signal_servicer, data_servicer, factor_servicer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Python gRPC research server")
    parser.add_argument("--port", type=int, default=8902, help="gRPC listen port")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    server, _, _ = serve(port=args.port)
    server.start()
    logger.info("Server started. Press Ctrl+C to stop.")
    server.wait_for_termination()
