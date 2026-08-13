import asyncio
import logging
import os
import sys
from enum import Enum

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .consensus import run_consensus, LITELLM_URL, LITELLM_KEY
from .models import ConsensusRequest, ConsensusResponse

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-consensus-api")

app = FastAPI(
    title="MCP Consensus REST API",
    description="Multi-model AI consensus via arbiter/worker pattern",
    version="0.1.0",
)


TOOL_MAP = {
    "design": "multi_ai_design",
    "review": "multi_ai_review",
    "implement": "multi_ai_implement",
}


class ToolName(str, Enum):
    design = "design"
    review = "review"
    implement = "implement"


class ConsensusAPIRequest(BaseModel):
    tool: ToolName = Field(
        default=ToolName.design,
        description="Consensus tool: design, review, or implement",
    )
    prompt: str = Field(..., description="The task, question, or code to evaluate")
    worker_models: list[str] | None = Field(
        default=None,
        description="Override default worker models. If not set, uses all available.",
    )
    arbiter_model: str | None = Field(
        default=None,
        description="Override default arbiter model.",
    )
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    dry_run: bool = Field(default=False)


@app.get("/health")
async def health():
    try:
        headers = {}
        if LITELLM_KEY:
            headers["Authorization"] = f"Bearer {LITELLM_KEY}"
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{LITELLM_URL}/health/liveliness", headers=headers,
            )
            litellm_ok = resp.status_code == 200
    except Exception:
        litellm_ok = False

    return {
        "status": "healthy" if litellm_ok else "degraded",
        "litellm": "connected" if litellm_ok else "unreachable",
        "litellm_url": LITELLM_URL,
    }


@app.get("/v1/models")
async def list_models():
    try:
        headers = {}
        if LITELLM_KEY:
            headers["Authorization"] = f"Bearer {LITELLM_KEY}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=10)) as client:
            resp = await client.get(
                f"{LITELLM_URL}/v1/models", headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            models = sorted(set(m["id"] for m in data.get("data", [])))
            return {"models": models, "count": len(models)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LiteLLM unavailable: {e}")


@app.post("/v1/consensus", response_model=ConsensusResponse)
async def consensus(req: ConsensusAPIRequest):
    inner = ConsensusRequest(
        prompt=req.prompt,
        worker_models=req.worker_models,
        arbiter_model=req.arbiter_model,
        temperature=req.temperature,
        timeout_seconds=req.timeout_seconds,
        dry_run=req.dry_run,
    )
    tool_name = TOOL_MAP[req.tool.value]
    result = await run_consensus(tool_name, inner)
    return result


def main():
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
