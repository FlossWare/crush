import asyncio
import json
import logging
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .consensus import run_consensus
from .models import ConsensusRequest

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-consensus")

INPUT_SCHEMA = ConsensusRequest.model_json_schema()

TOOLS = [
    Tool(
        name="multi_ai_design",
        description=(
            "Get multi-model AI analysis on architecture and design decisions. "
            "Fans out to N free AI models in parallel, then an arbiter synthesizes the results."
        ),
        inputSchema=INPUT_SCHEMA,
    ),
    Tool(
        name="multi_ai_review",
        description=(
            "Get multi-model code review analysis. "
            "Each model independently reviews the code, then an arbiter synthesizes findings."
        ),
        inputSchema=INPUT_SCHEMA,
    ),
    Tool(
        name="multi_ai_implement",
        description=(
            "Get multi-model implementation suggestions. "
            "Each model independently proposes an implementation, then an arbiter picks the best approach."
        ),
        inputSchema=INPUT_SCHEMA,
    ),
]

VALID_TOOLS = {t.name for t in TOOLS}

app = Server("mcp-consensus")


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in VALID_TOOLS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        request = ConsensusRequest(**arguments)
    except Exception as e:
        logger.warning("Invalid arguments for %s: %s", name, e)
        return [TextContent(type="text", text="Invalid arguments: check required fields (prompt is required)")]

    logger.info(
        "Tool=%s workers=%s arbiter=%s dry_run=%s",
        name,
        request.worker_models or "fleet-default",
        request.arbiter_model or "default",
        request.dry_run,
    )

    result = await run_consensus(name, request)

    output = {
        "synthesized_response": result.synthesized_response,
        "consensus_metadata": {
            "arbiter_model": result.arbiter_model,
            "execution_time_ms": result.execution_time_ms,
            "successful_workers": result.successful_workers,
            "failed_workers": [fw.model_dump() for fw in result.failed_workers],
        },
    }

    if result.raw_worker_responses:
        output["raw_worker_responses"] = [
            {"model": wr.model, "response": wr.response, "latency_ms": wr.latency_ms}
            for wr in result.raw_worker_responses
        ]

    return [TextContent(type="text", text=json.dumps(output, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def entry():
    asyncio.run(main())


if __name__ == "__main__":
    entry()
