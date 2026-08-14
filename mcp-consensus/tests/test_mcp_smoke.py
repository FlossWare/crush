"""End-to-end MCP protocol smoke tests.

Proves initialize → tools/list → tools/call across the real MCP boundary:
client JSON-RPC ↔ stdio transport ↔ server process.
"""

from __future__ import annotations

import json
import os
import sys

import pytest


def _server_env() -> dict[str, str]:
    """Inherit the test environment so the editable install is visible."""
    env = os.environ.copy()
    # Keep PATH so the same interpreter resolves; do not force LITELLM calls.
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


@pytest.mark.asyncio
async def test_mcp_stdio_initialize_list_call_dry_run():
    """Genuine protocol path: spawn server over stdio, handshake, list, call.

    This is the non-skippable confidence check for MCP SDK compatibility.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_consensus"],
        env=_server_env(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            assert init is not None

            tools_result = await session.list_tools()
            tools = tools_result.tools
            names = {t.name for t in tools}
            assert names == {
                "multi_ai_design",
                "multi_ai_review",
                "multi_ai_implement",
            }

            # Schemas must advertise the required prompt field
            for tool in tools:
                schema = getattr(tool, "input_schema", None) or getattr(
                    tool, "inputSchema", None
                )
                assert schema is not None
                props = schema.get("properties", {})
                required = schema.get("required", [])
                assert "prompt" in props
                assert "prompt" in required

            result = await session.call_tool(
                "multi_ai_design",
                arguments={"prompt": "stdio smoke test", "dry_run": True},
            )

            is_error = getattr(result, "is_error", None)
            if is_error is None:
                is_error = getattr(result, "isError", False)
            assert not is_error
            assert result.content, "expected non-empty tool content"

            text = result.content[0].text
            payload = json.loads(text)
            assert "DRY RUN" in payload["synthesized_response"]
            assert payload["consensus_metadata"]["execution_time_ms"] == 0
            assert "stdio smoke test" in payload["synthesized_response"]


@pytest.mark.asyncio
async def test_mcp_stdio_unknown_tool_is_error():
    """Protocol path returns is_error for unknown tool names."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_consensus"],
        env=_server_env(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "not_a_real_tool",
                arguments={"prompt": "x"},
            )
            is_error = getattr(result, "is_error", None)
            if is_error is None:
                is_error = getattr(result, "isError", False)
            assert is_error
            assert "Unknown tool" in result.content[0].text


@pytest.mark.asyncio
async def test_mcp_protocol_handlers_list_and_call():
    """Fast unit path: registered handlers + init options (not a protocol E2E)."""
    from unittest.mock import MagicMock

    from mcp.types import CallToolRequestParams

    from mcp_consensus.server import (
        _handle_call_tool,
        _handle_list_tools,
        app,
    )

    opts = app.create_initialization_options()
    assert opts is not None

    ctx = MagicMock(name="ServerRequestContext")
    listed = await _handle_list_tools(ctx, None)
    assert len(listed.tools) == 3

    call = await _handle_call_tool(
        ctx,
        CallToolRequestParams(
            name="multi_ai_review",
            arguments={"prompt": "handler smoke", "dry_run": True},
        ),
    )
    assert not call.is_error
    payload = json.loads(call.content[0].text)
    assert "DRY RUN" in payload["synthesized_response"]
