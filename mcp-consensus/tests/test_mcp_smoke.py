"""End-to-end MCP protocol smoke tests.

Exercises initialize → tools/list → tools/call through the MCP client/server
boundary (in-process when supported; otherwise handler-level protocol path).
"""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_mcp_inprocess_initialize_list_call_dry_run():
    """Prefer the SDK in-process Client(server) path when available."""
    from mcp_consensus.server import app

    try:
        from mcp import Client
    except ImportError:
        pytest.skip("mcp.Client not available in this SDK build")

    try:
        async with Client(app) as client:
            tools_result = await client.list_tools()
            tools = getattr(tools_result, "tools", tools_result)
            names = {t.name for t in tools}
            assert names == {
                "multi_ai_design",
                "multi_ai_review",
                "multi_ai_implement",
            }

            result = await client.call_tool(
                "multi_ai_design",
                {"prompt": "smoke test", "dry_run": True},
            )
            is_error = getattr(result, "is_error", None)
            if is_error is None:
                is_error = getattr(result, "isError", False)
            assert not is_error

            text = result.content[0].text
            payload = json.loads(text)
            assert "DRY RUN" in payload["synthesized_response"]
            assert payload["consensus_metadata"]["execution_time_ms"] == 0
    except TypeError as e:
        # Low-level Server may not be accepted by Client() in some builds.
        pytest.skip(f"In-process Client(app) not supported: {e}")
    except Exception as e:
        # Surface unexpected protocol failures rather than silently passing.
        if "not supported" in str(e).lower() or "transport" in str(e).lower():
            pytest.skip(f"In-process transport unavailable: {e}")
        raise


@pytest.mark.asyncio
async def test_mcp_protocol_handlers_initialize_list_call():
    """Always-available protocol path: registered handlers + init options."""
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
            arguments={"prompt": "protocol smoke", "dry_run": True},
        ),
    )
    assert not call.is_error
    payload = json.loads(call.content[0].text)
    assert "DRY RUN" in payload["synthesized_response"]
