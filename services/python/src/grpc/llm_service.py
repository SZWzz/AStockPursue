"""gRPC LLMService — AI chat and agent decision-making.

Wraps the agent loop (AgentLoop, ToolRegistry) behind the protobuf contract
defined in llm.proto.  Gracefully degrades when real LLM dependencies are
unavailable (test / CI environments).
"""
from __future__ import annotations

import logging

import grpc

from src.gen import llm_pb2, llm_pb2_grpc

logger = logging.getLogger(__name__)


class LLMServiceServicer(llm_pb2_grpc.LLMServiceServicer):
    """gRPC implementation of LLMService.

    Provides two RPCs:

    * **Chat** — simple text-in/text-out via ``run_agent_sync``.
    * **AgentDecide** — structured decision (action + params) via ``AgentLoop``.
    """

    def Chat(self, request, context):
        """Handle a simple chat message.

        Delegates to ``run_agent_sync()`` for a single-turn reply.
        Returns an empty ``ChatResponse`` on missing input or runtime error.
        """
        message = request.message
        if not message:
            if context is not None:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("message is required")
            return llm_pb2.ChatResponse(reply="")

        try:
            # Lazy import: the agent module may not be available in all
            # environments (test, CI).  Graceful degradation is intentional.
            from src.agent.loop import run_agent_sync

            result = run_agent_sync(message)
            reply = result.get("content", "") if isinstance(result, dict) else str(result)
            return llm_pb2.ChatResponse(reply=reply)

        except Exception as e:
            logger.exception("LLM chat failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
            return llm_pb2.ChatResponse(reply="")

    def AgentDecide(self, request, context):
        """Make a structured agent decision with context.

        Builds a minimal ``AgentLoop`` with a fresh ``ToolRegistry``, runs the
        query, and returns the extracted action and params.  Falls back to an
        empty response on any error (missing dependencies, runtime failure).
        """
        query = request.query
        ctx = dict(request.context) if request.context else {}

        try:
            from src.agent.loop import AgentLoop
            from src.agent.tools import ToolRegistry

            registry = ToolRegistry()
            agent = AgentLoop(registry=registry, memory=None, llm=None)
            result = agent.run(query)

            action = result.get("action", "") if isinstance(result, dict) else ""
            raw_params = result.get("params", {}) if isinstance(result, dict) else {}
            # Ensure all param values are strings (protobuf map<string,string>)
            params = {k: str(v) for k, v in raw_params.items()}
            return llm_pb2.AgentResponse(action=action, params=params)

        except Exception as e:
            logger.exception("Agent decision failed")
            if context is not None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
            return llm_pb2.AgentResponse(action="", params={})
