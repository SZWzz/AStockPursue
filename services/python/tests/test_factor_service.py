"""Tests for FactorService gRPC servicer."""
import pytest
from src.gen import factor_pb2
from src.grpc.factor_service import FactorServiceServicer


class TestFactorService:
    def test_compute_factor_constant(self):
        servicer = FactorServiceServicer()
        req = factor_pb2.FactorRequest(
            formula="ts_mean(close, 5)",
            symbols=["000001.SZ"],
            start_date="2026-01-01",
            end_date="2026-01-20",
        )
        resp = servicer.ComputeFactor(req, None)
        # With no real data, should return error
        assert resp.error != "" or len(resp.values) > 0

    def test_compute_factor_invalid_formula(self):
        servicer = FactorServiceServicer()
        req = factor_pb2.FactorRequest(
            formula="invalid >>> syntax",
            symbols=["000001.SZ"],
            start_date="2026-01-01",
            end_date="2026-01-20",
        )
        resp = servicer.ComputeFactor(req, None)
        assert resp.error != ""

    @pytest.mark.slow
    def test_start_gp_mining_config(self):
        servicer = FactorServiceServicer()
        req = factor_pb2.GPRequest(
            pool="a_share",
            generations=5,
            population_size=10,
            fitness_metric="composite",
        )
        # GP mining returns a generator/iterator
        gen = servicer.StartGPMining(req, None)
        results = list(gen)
        assert len(results) > 0
        # Each result should have a generation number
        assert results[0].generation >= 1
