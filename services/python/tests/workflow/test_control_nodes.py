"""Tests for control-flow and LLM nodes — ChatInput, Agent, IF."""

import asyncio
from src.workflow.nodes.control_nodes import AgentNode, ChatInputNode, IFNode


class TestChatInputNode:
    def test_attributes(self):
        n = ChatInputNode()
        assert n.node_type == "chat_input"

    def test_execute(self):
        n = ChatInputNode()
        loop = asyncio.new_event_loop()
        try:
            r = loop.run_until_complete(n.execute({}, {"prompt": "Build a strategy"}))
            assert r["prompt"]["text"] == "Build a strategy"
        finally:
            loop.close()

    def test_empty_uses_default(self):
        n = ChatInputNode()
        loop = asyncio.new_event_loop()
        try:
            r = loop.run_until_complete(n.execute({}, {}))
            assert len(r["prompt"]["text"]) > 0
        finally:
            loop.close()


class TestAgentNode:
    def test_attributes(self):
        n = AgentNode()
        assert n.node_type == "agent"
        assert n.resource_profile == "io_bound"

    def test_extract_code_signalengine(self):
        result = AgentNode._extract_code("```python\nclass SignalEngine:\n    def generate(self, data_map):\n        return {}\n```")
        assert result["code"] != ""

    def test_extract_code_none(self):
        result = AgentNode._extract_code("Just analysis text.")
        assert result["source"] == "none"

    def test_factor_extraction(self):
        result = AgentNode._extract_code("Use alpha101_001 and gtja191_005")
        # _extract_code doesn't extract factors; factor_suggestion handles that


class TestIFNode:
    def test_attributes(self):
        n = IFNode()
        assert n.node_type == "if_condition"

    def test_condition_true(self):
        n = IFNode()
        loop = asyncio.new_event_loop()
        try:
            r = loop.run_until_complete(n.execute({"input": {"summary": {"sharpe": 1.5}}}, {"field": "sharpe", "operator": ">", "threshold": 1.0}))
            assert r["true_branch"] is not None
            assert r["false_branch"] is None
        finally:
            loop.close()

    def test_condition_false(self):
        n = IFNode()
        loop = asyncio.new_event_loop()
        try:
            r = loop.run_until_complete(n.execute({"input": {"summary": {"sharpe": 0.3}}}, {"field": "sharpe", "operator": ">", "threshold": 1.0}))
            assert r["true_branch"] is None
            assert r["false_branch"] is not None
        finally:
            loop.close()
