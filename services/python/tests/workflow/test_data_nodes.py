"""Tests for StockUniverseNode and OHLCVLoaderNode."""

import asyncio


from src.workflow.nodes.data_nodes import StockUniverseNode, OHLCVLoaderNode, CSI300_CODES


class TestStockUniverseNode:
    def test_node_attributes(self):
        node = StockUniverseNode()
        assert node.node_type == "stock_universe"
        assert node.category == "data"
        assert len(node.outputs) == 1
        assert node.outputs[0].name == "codes"

    def test_default_preset(self):
        node = StockUniverseNode()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(node.execute({}, {}))
            assert "codes" in result
            assert len(result["codes"]) > 0
        finally:
            loop.close()

    def test_csi300_preset(self):
        node = StockUniverseNode()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(node.execute({}, {"preset": "csi300"}))
            assert result["codes"] == CSI300_CODES
        finally:
            loop.close()

    def test_custom_codes(self):
        node = StockUniverseNode()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(node.execute({}, {"preset": "custom", "custom_codes": "000001.SZ,600519.SH,000858.SZ"}))
            assert result["codes"] == ["000001.SZ", "600519.SH", "000858.SZ"]
        finally:
            loop.close()

    def test_custom_empty_falls_back_to_default(self):
        node = StockUniverseNode()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(node.execute({}, {"preset": "custom", "custom_codes": ""}))
            assert len(result["codes"]) > 0
        finally:
            loop.close()


class TestOHLCVLoaderNode:
    def test_node_attributes(self):
        node = OHLCVLoaderNode()
        assert node.node_type == "ohlcv_loader"
        assert node.category == "data"
        assert node.resource_profile == "io_bound"
        assert len(node.inputs) == 1
        assert node.inputs[0].name == "codes"
        assert len(node.outputs) == 1

    def test_empty_codes_returns_empty(self):
        node = OHLCVLoaderNode()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(node.execute({"codes": []}, {}))
            assert result == {"ohlcv_data": {}}
        finally:
            loop.close()
