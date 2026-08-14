import logging
import os
import sys
from enum import Enum

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .consensus import LITELLM_KEY, LITELLM_URL, _parse_int_env, run_consensus
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
        description="Override default worker models. If not set, uses the configured fleet.",
    )
    arbiter_model: str | None = Field(
        default=None,
        description="Override default arbiter model.",
    )
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    arbiter_temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Arbiter synthesis temperature. Defaults to 0.3.",
    )
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    arbiter_timeout_seconds: int | None = Field(
        default=None,
        ge=5,
        le=600,
        description="Arbiter timeout in seconds. Defaults to timeout_seconds.",
    )
    dry_run: bool = Field(default=False)


@app.get("/health")
async def health():
    try:
        headers = {}
        if LITELLM_KEY:
            headers["Authorization"] = f"Bearer {LITELLM_KEY}"
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{LITELLM_URL}/health/liveliness",
                headers=headers,
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
                f"{LITELLM_URL}/v1/models",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            models = sorted(set(m["id"] for m in data.get("data", [])))
            return {"models": models, "count": len(models)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LiteLLM unavailable: {e}")


@app.post("/v1/consensus", response_model=ConsensusResponse)
async def consensus(req: ConsensusAPIRequest):
    try:
        inner = ConsensusRequest(
            prompt=req.prompt,
            worker_models=req.worker_models,
            arbiter_model=req.arbiter_model,
            temperature=req.temperature,
            arbiter_temperature=req.arbiter_temperature,
            timeout_seconds=req.timeout_seconds,
            arbiter_timeout_seconds=req.arbiter_timeout_seconds,
            dry_run=req.dry_run,
        )
    except Exception as e:
        logger.warning("Invalid consensus request: %s", e)
        raise HTTPException(status_code=422, detail="Invalid request parameters")
    tool_name = TOOL_MAP[req.tool.value]
    try:
        result = await run_consensus(tool_name, inner)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Consensus failed: %s", e)
        raise HTTPException(status_code=502, detail="Consensus execution failed")
    return result


def main():
    host = os.environ.get("API_HOST", "127.0.0.1")
    # Validate like other numeric config so bad values fail clearly at startup.
    port = _parse_int_env("API_PORT", 8080, 1, 65535)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
