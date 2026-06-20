"""Tests for AnalysisService gRPC servicer."""
import pytest
from src.gen import analysis_pb2
from src.grpc.analysis_service import AnalysisServiceServicer


class TestAnalysisService:
    def test_calc_attribution_empty_request(self):
        servicer = AnalysisServiceServicer()
        req = analysis_pb2.AttributionRequest(
            portfolio_id="",
            start_date="",
            end_date="",
        )
        resp = servicer.CalcAttribution(req, None)
        # Empty request should return error
        assert resp.error != ""

    def test_calc_correlation_empty_symbols(self):
        servicer = AnalysisServiceServicer()
        req = analysis_pb2.CorrelationRequest(
            symbols=[],
            start_date="2026-01-01",
            end_date="2026-01-20",
        )
        resp = servicer.CalcCorrelation(req, None)
        assert resp.error != "" or len(resp.matrix) == 0

    def test_stress_test_empty_portfolio(self):
        servicer = AnalysisServiceServicer()
        req = analysis_pb2.StressTestRequest(
            portfolio_id="",
            scenarios=["2008_crisis"],
        )
        resp = servicer.StressTest(req, None)
        assert resp.error != ""
