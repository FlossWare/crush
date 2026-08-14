"""MCP protocol integration tests.

Exercises the server through the MCP SDK v2 handler API:
  on_list_tools(ctx, params) -> ListToolsResult
  on_call_tool(ctx, params) -> CallToolResult
"""

import json
from unittest.mock import MagicMock

import pytest
import respx

from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
)

from mcp_consensus.server import (
    TOOLS,
    VALID_TOOLS,
    _handle_call_tool,
    _handle_list_tools,
    app,
)


def _ctx():
    return MagicMock(name="ServerRequestContext")


@pytest.mark.asyncio
class TestMCPProtocol:
    async def test_initialize_options(self):
        """Server produces valid initialization options."""
        opts = app.create_initialization_options()
        assert opts is not None

    async def test_list_tools(self):
        """tools/list returns all three tools with valid schemas."""
        result = await _handle_list_tools(_ctx(), None)
        assert isinstance(result, ListToolsResult)
        assert len(result.tools) == 3

        names = {t.name for t in result.tools}
        assert names == {"multi_ai_design", "multi_ai_review", "multi_ai_implement"}

        for tool in result.tools:
            schema = tool.input_schema
            assert schema.get("type") == "object"
            assert "prompt" in schema.get("properties", {})
            assert "prompt" in schema.get("required", [])

    async def test_list_tools_with_pagination_params(self):
        result = await _handle_list_tools(_ctx(), PaginatedRequestParams())
        assert len(result.tools) == 3

    @respx.mock
    async def test_call_tool_dry_run(self):
        """tools/call with dry_run=True returns prompts, makes no network calls."""
        params = CallToolRequestParams(
            name="multi_ai_design",
            arguments={"prompt": "test", "dry_run": True},
        )
        result = await _handle_call_tool(_ctx(), params)
        assert isinstance(result, CallToolResult)
        assert not result.is_error

        output = json.loads(result.content[0].text)
        assert "DRY RUN" in output["synthesized_response"]
        assert output["consensus_metadata"]["execution_time_ms"] == 0

    @respx.mock
    async def test_call_tool_live(self):
        """tools/call with mocked workers completes successfully."""
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

        params = CallToolRequestParams(
            name="multi_ai_review",
            arguments={"prompt": "Review this", "worker_models": ["test-model"]},
        )
        result = await _handle_call_tool(_ctx(), params)
        assert isinstance(result, CallToolResult)
        assert not result.is_error

        output = json.loads(result.content[0].text)
        assert output["consensus_metadata"]["successful_workers"] == ["test-model"]

    async def test_call_tool_unknown(self):
        """tools/call with unknown tool name returns an error result."""
        params = CallToolRequestParams(name="nonexistent", arguments={"prompt": "test"})
        result = await _handle_call_tool(_ctx(), params)
        assert isinstance(result, CallToolResult)
        assert result.is_error
        assert "Unknown tool" in result.content[0].text

    async def test_call_tool_missing_prompt(self):
        """tools/call without required 'prompt' returns an error result."""
        params = CallToolRequestParams(name="multi_ai_design", arguments={})
        result = await _handle_call_tool(_ctx(), params)
        assert isinstance(result, CallToolResult)
        assert result.is_error
        assert "Invalid arguments" in result.content[0].text

    @respx.mock
    async def test_each_tool_invocable(self):
        """All three tools can be called via the protocol (dry-run)."""
        for tool_name in ["multi_ai_design", "multi_ai_review", "multi_ai_implement"]:
            params = CallToolRequestParams(
                name=tool_name,
                arguments={"prompt": f"Test {tool_name}", "dry_run": True},
            )
            result = await _handle_call_tool(_ctx(), params)
            assert not result.is_error
            output = json.loads(result.content[0].text)
            assert "DRY RUN" in output["synthesized_response"]

    async def test_tool_names_match_prompts(self):
        """Each tool name has a corresponding worker prompt defined."""
        from mcp_consensus.prompts import WORKER_PROMPTS

        result = await _handle_list_tools(_ctx(), None)
        for tool in result.tools:
            assert tool.name in WORKER_PROMPTS, f"No worker prompt for {tool.name}"

    def test_tools_and_valid_set_aligned(self):
        assert VALID_TOOLS == {t.name for t in TOOLS}
