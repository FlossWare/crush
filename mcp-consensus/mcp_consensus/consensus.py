import asyncio
import logging
import os
import time

import httpx

from .models import (
    ConsensusRequest,
    ConsensusResponse,
    FailedWorker,
    WorkerResponse,
    DEFAULT_ARBITER,
    DEFAULT_WORKERS,
)
from .prompts import build_arbiter_prompt, build_worker_prompt

logger = logging.getLogger("mcp-consensus")

LITELLM_URL = os.environ.get("LITELLM_URL", "http://localhost:4000")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

MAX_CONCURRENT_WORKERS = min(int(os.environ.get("MAX_CONCURRENT_WORKERS", "10")), 50)


async def call_model(
    client: httpx.AsyncClient,
    model: str,
    messages: list[dict],
    temperature: float,
) -> str:
    headers = {"Content-Type": "application/json"}
    if LITELLM_KEY:
        headers["Authorization"] = f"Bearer {LITELLM_KEY}"

    resp = await client.post(
        f"{LITELLM_URL}/v1/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        },
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


WORKER_RETRIES = int(os.environ.get("WORKER_RETRIES", "2"))


async def call_worker(
    client: httpx.AsyncClient,
    model: str,
    tool_name: str,
    user_prompt: str,
    temperature: float,
    timeout_seconds: int,
    semaphore: asyncio.Semaphore,
) -> WorkerResponse | FailedWorker:
    messages = build_worker_prompt(tool_name, user_prompt)
    start = time.monotonic()
    async with semaphore:
        last_error = None
        for attempt in range(1 + WORKER_RETRIES):
            try:
                response = await asyncio.wait_for(
                    call_model(client, model, messages, temperature),
                    timeout=timeout_seconds,
                )
                latency = int((time.monotonic() - start) * 1000)
                logger.info("Worker %s succeeded (%dms)", model, latency)
                return WorkerResponse(model=model, response=response, latency_ms=latency)
            except asyncio.TimeoutError:
                logger.warning("Worker %s timed out after %ds", model, timeout_seconds)
                return FailedWorker(model=model, error=f"Timeout after {timeout_seconds}s")
            except Exception as e:
                last_error = e
                if attempt < WORKER_RETRIES:
                    delay = 2 ** attempt
                    logger.info("Worker %s attempt %d failed, retrying in %ds", model, attempt + 1, delay)
                    await asyncio.sleep(delay)
        logger.warning("Worker %s failed after %d attempts: %s", model, 1 + WORKER_RETRIES, last_error)
        return FailedWorker(model=model, error=str(last_error))


async def query_available_models(client: httpx.AsyncClient) -> list[str]:
    try:
        headers = {}
        if LITELLM_KEY:
            headers["Authorization"] = f"Bearer {LITELLM_KEY}"
        resp = await client.get(
            f"{LITELLM_URL}/v1/models",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return sorted(set(m["id"] for m in data.get("data", [])))
    except Exception:
        return []


async def run_consensus(
    tool_name: str,
    request: ConsensusRequest,
) -> ConsensusResponse:
    start = time.monotonic()

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=600)) as client:
        # Resolve worker models
        if request.worker_models:
            workers = request.worker_models
        else:
            available = await query_available_models(client)
            workers = available if available else DEFAULT_WORKERS

        arbiter = request.arbiter_model or os.environ.get("DEFAULT_ARBITER", DEFAULT_ARBITER)

        # Dry run — return prompts without calling models
        if request.dry_run:
            from .prompts import WORKER_PROMPTS, ARBITER_SYSTEM_PROMPT
            dry_response = (
                f"DRY RUN — no API calls made.\n\n"
                f"Workers ({len(workers)}): {', '.join(workers)}\n"
                f"Arbiter: {arbiter}\n\n"
                f"Worker system prompt:\n{WORKER_PROMPTS.get(tool_name, 'N/A')}\n\n"
                f"Arbiter system prompt:\n{ARBITER_SYSTEM_PROMPT.format(worker_count=len(workers))}\n\n"
                f"User prompt:\n{request.prompt}"
            )
            return ConsensusResponse(
                synthesized_response=dry_response,
                arbiter_model=arbiter,
                execution_time_ms=0,
                successful_workers=[],
                failed_workers=[],
                raw_worker_responses=[],
            )

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)

        tasks = [
            call_worker(
                client, model, tool_name, request.prompt,
                request.temperature, request.timeout_seconds, semaphore,
            )
            for model in workers
        ]
        results = await asyncio.gather(*tasks)

        successful = [r for r in results if isinstance(r, WorkerResponse)]
        failed = [r for r in results if isinstance(r, FailedWorker)]

        if not successful:
            error_details = "; ".join(f"{f.model}: {f.error}" for f in failed)
            return ConsensusResponse(
                synthesized_response=f"All {len(workers)} workers failed. Errors: {error_details}",
                arbiter_model=arbiter,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                successful_workers=[],
                failed_workers=failed,
                raw_worker_responses=[],
            )

        # Build arbiter prompt from successful responses
        arbiter_messages = build_arbiter_prompt(
            tool_name,
            request.prompt,
            [{"model": w.model, "response": w.response} for w in successful],
        )

        try:
            synthesis = await asyncio.wait_for(
                call_model(client, arbiter, arbiter_messages, request.temperature),
                timeout=request.timeout_seconds,
            )
        except Exception as e:
            synthesis = (
                f"Arbiter ({arbiter}) failed: {e}\n\n"
                f"Returning raw worker responses without synthesis.\n\n"
                + "\n---\n".join(
                    f"**{w.model}:**\n{w.response}" for w in successful
                )
            )

    return ConsensusResponse(
        synthesized_response=synthesis,
        arbiter_model=arbiter,
        execution_time_ms=int((time.monotonic() - start) * 1000),
        successful_workers=[w.model for w in successful],
        failed_workers=failed,
        raw_worker_responses=successful,
    )
