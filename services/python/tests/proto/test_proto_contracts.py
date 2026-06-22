"""Proto contract tests: verify generated Python stubs match the .proto definitions.

These tests validate that the protobuf Python classes can be instantiated,
have the correct field types, and survive serialization round-trips.
"""
import pytest

# ── Check if generated stubs are available ──
try:
    from src.gen import common_pb2
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False

skip_if_no_stubs = pytest.mark.skipif(
    not _HAS_STUBS,
    reason="Generated proto stubs not found. Run: cd services/proto && buf generate",
)


# ============================================================
# common_pb2: Bar, Position, Order
# ============================================================

@skip_if_no_stubs
class TestCommonBar:
    def test_bar_instantiation(self):
        bar = common_pb2.Bar()
        assert bar.symbol == ""
        assert bar.open == 0.0
        assert bar.high == 0.0
        assert bar.low == 0.0
        assert bar.close == 0.0
        assert bar.volume == 0
        assert bar.timestamp == 0
        assert bar.frequency == ""

    def test_bar_field_types(self):
        bar = common_pb2.Bar()
        assert isinstance(bar.symbol, str)
        assert isinstance(bar.open, float)
        assert isinstance(bar.high, float)
        assert isinstance(bar.low, float)
        assert isinstance(bar.close, float)
        assert isinstance(bar.volume, int)
        assert isinstance(bar.timestamp, int)
        assert isinstance(bar.frequency, str)

    def test_bar_set_fields(self):
        bar = common_pb2.Bar(
            symbol="000001.SZ",
            open=10.5,
            high=11.0,
            low=10.0,
            close=10.8,
            volume=1000000,
            timestamp=1719000000,
            frequency="1d",
        )
        assert bar.symbol == "000001.SZ"
        assert bar.open == 10.5
        assert bar.high == 11.0
        assert bar.low == 10.0
        assert bar.close == 10.8
        assert bar.volume == 1000000
        assert bar.timestamp == 1719000000
        assert bar.frequency == "1d"


@skip_if_no_stubs
class TestCommonPosition:
    def test_position_instantiation(self):
        pos = common_pb2.Position()
        assert pos.symbol == ""
        assert pos.size == 0.0
        assert pos.entry_price == 0.0
        assert pos.current_price == 0.0
        assert pos.pnl == 0.0
        assert pos.side == ""

    def test_position_field_types(self):
        pos = common_pb2.Position()
        assert isinstance(pos.symbol, str)
        assert isinstance(pos.size, float)
        assert isinstance(pos.entry_price, float)
        assert isinstance(pos.current_price, float)
        assert isinstance(pos.pnl, float)
        assert isinstance(pos.side, str)


@skip_if_no_stubs
class TestCommonOrder:
    def test_order_instantiation(self):
        order = common_pb2.Order()
        assert order.id == ""
        assert order.symbol == ""
        assert order.side == ""
        assert order.type == ""
        assert order.price == 0.0
        assert order.quantity == 0.0
        assert order.status == ""

    def test_order_set_fields(self):
        order = common_pb2.Order(
            id="ord-001",
            symbol="000001.SZ",
            side="buy",
            type="limit",
            price=10.5,
            quantity=100.0,
            status="pending",
        )
        assert order.id == "ord-001"
        assert order.symbol == "000001.SZ"
        assert order.side == "buy"
        assert order.type == "limit"
        assert order.price == 10.5
        assert order.quantity == 100.0
        assert order.status == "pending"


# ============================================================
# data_pb2: FetchBarsRequest, FetchBarsResponse
# ============================================================

@pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
class TestDataProto:
    def test_fetch_bars_request(self):
        from src.gen import data_pb2
        req = data_pb2.FetchBarsRequest(
            source="mootdx",
            symbol="000001.SZ",
            start_date="2026-01-01",
            end_date="2026-01-31",
            frequency="1d",
        )
        assert req.source == "mootdx"
        assert req.symbol == "000001.SZ"

    def test_fetch_bars_response_has_bars(self):
        from src.gen import data_pb2
        resp = data_pb2.FetchBarsResponse()
        # bars is a repeated field, should be iterable
        assert hasattr(resp, "bars")
        assert len(resp.bars) == 0
        assert resp.error == ""


# ============================================================
# factor_pb2: FactorRequest, FactorResponse
# ============================================================

class TestFactorProto:
    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_factor_request_fields(self):
        from src.gen import factor_pb2
        req = factor_pb2.FactorRequest(
            formula="ts_mean(close, 5)",
            symbols=["000001.SZ", "000002.SZ"],
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
        assert req.formula == "ts_mean(close, 5)"
        assert len(req.symbols) == 2
        assert req.symbols[0] == "000001.SZ"

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_factor_response_has_values_map(self):
        from src.gen import factor_pb2
        resp = factor_pb2.FactorResponse()
        assert hasattr(resp, "values")
        assert len(resp.values) == 0
        assert resp.error == ""

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_factor_round_trip(self):
        from src.gen import factor_pb2
        resp = factor_pb2.FactorResponse(
            values={"000001.SZ": 0.85},
            error="",
        )
        data = resp.SerializeToString()
        resp2 = factor_pb2.FactorResponse()
        resp2.ParseFromString(data)
        assert resp2.values["000001.SZ"] == 0.85


# ============================================================
# signal_pb2: SignalRequest, SignalResponse
# ============================================================

class TestSignalProto:
    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_signal_request_with_bars(self):
        from src.gen import signal_pb2
        bar = common_pb2.Bar(symbol="000001.SZ", close=10.5)
        req = signal_pb2.SignalRequest(
            strategy_name="momentum",
            bars=[bar],
            mode="backtest",
        )
        assert req.strategy_name == "momentum"
        assert len(req.bars) == 1
        assert req.bars[0].symbol == "000001.SZ"

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_signal_response_has_weights_map(self):
        from src.gen import signal_pb2
        resp = signal_pb2.SignalResponse()
        assert hasattr(resp, "weights")
        assert len(resp.weights) == 0
        assert resp.error == ""


# ============================================================
# workflow_pb2: WorkflowRequest, WorkflowResponse
# ============================================================

class TestWorkflowProto:
    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_workflow_request_fields(self):
        from src.gen import workflow_pb2
        req = workflow_pb2.WorkflowRequest(
            workflow_id="wf-001",
            params={"key": "value"},
        )
        assert req.workflow_id == "wf-001"
        assert req.params["key"] == "value"

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_workflow_response_status_and_error(self):
        from src.gen import workflow_pb2
        resp = workflow_pb2.WorkflowResponse()
        assert hasattr(resp, "status")
        assert hasattr(resp, "error")
        assert resp.status == ""
        assert resp.error == ""


# ============================================================
# llm_pb2: ChatRequest/ChatResponse, AgentRequest/AgentResponse
# ============================================================

class TestLLMProto:
    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_chat_request_response(self):
        from src.gen import llm_pb2
        req = llm_pb2.ChatRequest(message="Hello")
        assert req.message == "Hello"

        resp = llm_pb2.ChatResponse(reply="Hi there")
        assert resp.reply == "Hi there"

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_agent_request_response(self):
        from src.gen import llm_pb2
        req = llm_pb2.AgentRequest(
            query="buy AAPL",
            context={"market": "US"},
        )
        assert req.query == "buy AAPL"
        assert req.context["market"] == "US"

        resp = llm_pb2.AgentResponse(
            action="place_order",
            params={"symbol": "AAPL", "side": "buy"},
        )
        assert resp.action == "place_order"
        assert resp.params["symbol"] == "AAPL"


# ============================================================
# analysis_pb2: AttributionRequest/Response
# ============================================================

class TestAnalysisProto:
    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_attribution_request_fields(self):
        from src.gen import analysis_pb2
        req = analysis_pb2.AttributionRequest(
            portfolio_id="pf-001",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
        assert req.portfolio_id == "pf-001"
        assert req.start_date == "2026-01-01"
        assert req.end_date == "2026-01-31"

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_attribution_response_factors_map(self):
        from src.gen import analysis_pb2
        resp = analysis_pb2.AttributionResponse(
            factors={"momentum": 0.05, "size": 0.02},
        )
        assert resp.factors["momentum"] == 0.05
        assert resp.error == ""


# ============================================================
# Serialization round-trip
# ============================================================

class TestSerializationRoundTrip:
    """Verify that messages survive serialize -> deserialize."""

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_bar_round_trip(self):
        bar = common_pb2.Bar(
            symbol="000001.SZ",
            open=10.0, high=11.0, low=9.5, close=10.8,
            volume=5000000, timestamp=1719000000,
            frequency="1d",
        )
        data = bar.SerializeToString()
        bar2 = common_pb2.Bar()
        bar2.ParseFromString(data)
        assert bar2.symbol == bar.symbol
        assert bar2.open == bar.open
        assert bar2.close == bar.close
        assert bar2.volume == bar.volume
        assert bar2.timestamp == bar.timestamp

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_position_round_trip(self):
        pos = common_pb2.Position(
            symbol="000001.SZ",
            size=100.0,
            entry_price=10.0,
            current_price=11.0,
            pnl=100.0,
            side="long",
        )
        data = pos.SerializeToString()
        pos2 = common_pb2.Position()
        pos2.ParseFromString(data)
        assert pos2.symbol == pos.symbol
        assert pos2.size == pos.size
        assert pos2.pnl == pos.pnl

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_order_round_trip(self):
        order = common_pb2.Order(
            id="ord-001", symbol="000001.SZ", side="buy",
            type="limit", price=10.5, quantity=100.0, status="pending",
        )
        data = order.SerializeToString()
        order2 = common_pb2.Order()
        order2.ParseFromString(data)
        assert order2.id == order.id
        assert order2.symbol == order.symbol
        assert order2.status == order.status

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_chat_round_trip(self):
        from src.gen import llm_pb2
        req = llm_pb2.ChatRequest(message="test message")
        data = req.SerializeToString()
        req2 = llm_pb2.ChatRequest()
        req2.ParseFromString(data)
        assert req2.message == req.message

    @pytest.mark.skipif(not _HAS_STUBS, reason="Generated proto stubs not found.")
    def test_workflow_round_trip(self):
        from src.gen import workflow_pb2
        resp = workflow_pb2.WorkflowResponse(
            status="completed",
            error="",
        )
        data = resp.SerializeToString()
        resp2 = workflow_pb2.WorkflowResponse()
        resp2.ParseFromString(data)
        assert resp2.status == "completed"
        assert resp2.error == ""
