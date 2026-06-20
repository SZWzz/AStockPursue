"""Tests for LLMService gRPC servicer."""
import pytest
from src.gen import llm_pb2
from src.grpc.llm_service import LLMServiceServicer


class TestLLMService:
    def test_agent_decide_smoke(self):
        """AgentDecide should return a valid AgentResponse without raising."""
        servicer = LLMServiceServicer()
        req = llm_pb2.AgentRequest(
            query="analyze AAPL",
            context={"risk_level": "low", "max_positions": "5"},
        )
        resp = servicer.AgentDecide(req, None)
        # AgentDecide should return a valid response; in test env the agent
        # may not be available so we just verify the response is well-typed.
        assert isinstance(resp, llm_pb2.AgentResponse)

    def test_chat_empty_message(self):
        """Chat with empty message should return empty reply."""
        servicer = LLMServiceServicer()
        req = llm_pb2.ChatRequest(message="")
        resp = servicer.Chat(req, None)
        assert isinstance(resp, llm_pb2.ChatResponse)
        assert resp.reply == ""

    def test_chat_smoke(self):
        """Chat with a valid message should return a ChatResponse."""
        servicer = LLMServiceServicer()
        req = llm_pb2.ChatRequest(message="Hello")
        resp = servicer.Chat(req, None)
        assert isinstance(resp, llm_pb2.ChatResponse)
