"""MCP protocol integration tests.

Exercises the server through the actual MCP SDK types:
  ListToolsRequest → ListToolsResult
  CallToolRequest → CallToolResult
"""

import json

import pytest
import respx

from mcp.types import (
    CallToolRequest,
    CallToolRequestParams,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    TextContent,
)

from mcp_consensus.server import app


def _list_tools_request():
    return ListToolsRequest(method="tools/list")


def _call_tool_request(name: str, arguments: dict):
    return CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(name=name, arguments=arguments),
    )


@pytest.mark.asyncio
class TestMCPProtocol:
    async def test_initialize_options(self):
        """Server produces valid initialization options."""
        opts = app.create_initialization_options()
        assert opts is not None

    async def test_list_tools(self):
        """tools/list returns all three tools with valid schemas."""
        handler = app.get_request_handler("tools/list")
        assert handler is not None

        result = await handler.handler(_list_tools_request())
        assert isinstance(result, ListToolsResult)
        assert len(result.tools) == 3

        names = {t.name for t in result.tools}
        assert names == {"multi_ai_design", "multi_ai_review", "multi_ai_implement"}

        for tool in result.tools:
            schema = tool.input_schema
            assert schema.get("type") == "object"
            assert "prompt" in schema.get("properties", {})
            assert "prompt" in schema.get("required", [])

    @respx.mock
    async def test_call_tool_dry_run(self):
        """tools/call with dry_run=True returns prompts, makes no network calls."""
        handler = app.get_request_handler("tools/call")

        result = await handler.handler(
            _call_tool_request("multi_ai_design", {"prompt": "test", "dry_run": True})
        )
        assert isinstance(result, CallToolResult)
        assert not result.is_error

        output = json.loads(result.content[0].text)
        assert "DRY RUN" in output["synthesized_response"]
        assert output["consensus_metadata"]["execution_time_ms"] == 0

    @respx.mock
    async def test_call_tool_live(self):
        """tools/call with mocked workers completes successfully."""
        handler = app.get_request_handler("tools/call")
        call_count = 0

        def route_handler(request):
            nonlocal call_count
            call_count += 1
            return respx.MockResponse(
                200,
                json={"choices": [{"message": {"content": f"resp {call_count}"}}]},
            )

        respx.post("http://litellm-test:4000/v1/chat/completions").mock(
            side_effect=route_handler
        )

        result = await handler.handler(
            _call_tool_request(
                "multi_ai_review",
                {"prompt": "Review this", "worker_models": ["test-model"]},
            )
        )
        assert isinstance(result, CallToolResult)
        assert not result.is_error

        output = json.loads(result.content[0].text)
        assert output["consensus_metadata"]["successful_workers"] == ["test-model"]

    async def test_call_tool_unknown(self):
        """tools/call with unknown tool name returns an error result."""
        handler = app.get_request_handler("tools/call")
        result = await handler.handler(
            _call_tool_request("nonexistent", {"prompt": "test"})
        )
        assert isinstance(result, CallToolResult)
        assert result.is_error
        assert "Unknown tool" in result.content[0].text

    async def test_call_tool_missing_prompt(self):
        """tools/call without required 'prompt' returns an error result."""
        handler = app.get_request_handler("tools/call")
        result = await handler.handler(
            _call_tool_request("multi_ai_design", {})
        )
        assert isinstance(result, CallToolResult)
        assert result.is_error
        assert "Invalid arguments" in result.content[0].text

    @respx.mock
    async def test_each_tool_invocable(self):
        """All three tools can be called via the protocol (dry-run)."""
        handler = app.get_request_handler("tools/call")

        for tool_name in ["multi_ai_design", "multi_ai_review", "multi_ai_implement"]:
            result = await handler.handler(
                _call_tool_request(tool_name, {"prompt": f"Test {tool_name}", "dry_run": True})
            )
            assert not result.is_error
            output = json.loads(result.content[0].text)
            assert "DRY RUN" in output["synthesized_response"]

    async def test_tool_names_match_prompts(self):
        """Each tool name has a corresponding worker prompt defined."""
        from mcp_consensus.prompts import WORKER_PROMPTS

        handler = app.get_request_handler("tools/list")
        result = await handler.handler(_list_tools_request())
        for tool in result.tools:
            assert tool.name in WORKER_PROMPTS, f"No worker prompt for {tool.name}"
