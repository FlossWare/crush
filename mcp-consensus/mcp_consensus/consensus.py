import asyncio
import logging
import os
import random
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


def _parse_int_env(name: str, default: int, min_val: int, max_val: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        val = int(raw)
    except ValueError:
        raise SystemExit(
            f"Configuration error: {name}={raw!r} is not a valid integer"
        )
    if val < min_val or val > max_val:
        raise SystemExit(
            f"Configuration error: {name}={val} must be between {min_val} and {max_val}"
        )
    return val


MAX_CONCURRENT_WORKERS = _parse_int_env("MAX_CONCURRENT_WORKERS", 10, 1, 50)
WORKER_RETRIES = _parse_int_env("WORKER_RETRIES", 2, 0, 10)

_fleet_env = os.environ.get("WORKER_FLEET", "")
CONFIGURED_WORKERS = (
    [m.strip() for m in _fleet_env.split(",") if m.strip()]
    if _fleet_env
    else list(DEFAULT_WORKERS)
)

_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)


def _client_safe_error(exc: Exception) -> str:
    """Client-facing error token — type name only, no message body."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTPStatusError:{exc.response.status_code}"
    return type(exc).__name__


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
    choices = data.get("choices")
    if not choices:
        raise ValueError(f"Empty choices in response from {model}")
    return choices[0]["message"]["content"]


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, asyncio.TimeoutError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status >= 500 or status == 429
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout)):
        return True
    return False


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
    deadline = start + timeout_seconds
    last_error = None
    for attempt in range(1 + WORKER_RETRIES):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            last_error = last_error or asyncio.TimeoutError()
            break
        try:
            async with semaphore:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError()
                call_start = time.monotonic()
                response = await asyncio.wait_for(
                    call_model(client, model, messages, temperature),
                    timeout=remaining,
                )
            latency = int((time.monotonic() - call_start) * 1000)
            logger.info("Worker %s succeeded (%dms)", model, latency)
            return WorkerResponse(model=model, response=response, latency_ms=latency)
        except Exception as e:
            last_error = e
            if not _is_retryable(e):
                logger.warning("Worker %s failed with non-retryable error: %s", model, e)
                return FailedWorker(model=model, error=_client_safe_error(e))
            if attempt < WORKER_RETRIES:
                delay = min(
                    (2 ** attempt) + random.uniform(0, 1),
                    max(0, deadline - time.monotonic()),
                )
                if delay <= 0:
                    break
                logger.info(
                    "Worker %s attempt %d failed (%s), retrying in %.1fs",
                    model, attempt + 1, type(e).__name__, delay,
                )
                await asyncio.sleep(delay)
    logger.warning(
        "Worker %s failed after %d attempts: %s",
        model,
        1 + WORKER_RETRIES,
        last_error,
    )
    return FailedWorker(
        model=model,
        error=_client_safe_error(last_error) if last_error else "UnknownError",
    )


def _resolve_workers(request: ConsensusRequest) -> list[str]:
    if request.worker_models is not None:
        return request.worker_models
    return list(CONFIGURED_WORKERS)


def _concat_worker_responses(successful: list[WorkerResponse]) -> str:
    """Concatenate successful worker outputs for degraded arbiter fallback."""
    parts: list[str] = []
    for i, w in enumerate(successful, 1):
        parts.append(
            f"{'=' * 60}\n"
            f"MODEL {i}: {w.model}\n"
            f"{'=' * 60}\n"
            f"{w.response}\n"
        )
    return "".join(parts).rstrip()


async def run_consensus(
    tool_name: str,
    request: ConsensusRequest,
) -> ConsensusResponse:
    start = time.monotonic()
    workers = _resolve_workers(request)
    arbiter = request.arbiter_model or os.environ.get("DEFAULT_ARBITER", DEFAULT_ARBITER)

    # Empty fleet is always invalid — including dry-run — so clients get a
    # consistent error rather than a dry-run report of zero workers.
    if not workers:
        raise ValueError(
            "No worker models configured. Set WORKER_FLEET env var or pass worker_models."
        )

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

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=600)) as client:
        tasks = [
            call_worker(
                client,
                model,
                tool_name,
                request.prompt,
                request.temperature,
                request.timeout_seconds,
                _SEMAPHORE,
            )
            for model in workers
        ]
        results = await asyncio.gather(*tasks)

        successful = [r for r in results if isinstance(r, WorkerResponse)]
        failed = [r for r in results if isinstance(r, FailedWorker)]

        if not successful:
            error_details = "; ".join(f"{f.model}: {f.error}" for f in failed)
            return ConsensusResponse(
                synthesized_response=(
                    f"All {len(workers)} workers failed. Errors: {error_details}"
                ),
                arbiter_model=arbiter,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                successful_workers=[],
                failed_workers=failed,
                raw_worker_responses=[],
            )

        arbiter_messages = build_arbiter_prompt(
            tool_name,
            request.prompt,
            [{"model": w.model, "response": w.response} for w in successful],
        )

        arbiter_temp = (
            request.arbiter_temperature
            if request.arbiter_temperature is not None
            else 0.3
        )
        arbiter_timeout = request.arbiter_timeout_seconds or request.timeout_seconds

        arbiter_error = False
        try:
            synthesis = await asyncio.wait_for(
                call_model(client, arbiter, arbiter_messages, arbiter_temp),
                timeout=arbiter_timeout,
            )
        except Exception as e:
            # Documented contract: fall back to concatenated raw worker output
            # so MCP clients that only read synthesized_response still get value.
            arbiter_error = True
            concatenated = _concat_worker_responses(successful)
            synthesis = (
                f"Arbiter ({arbiter}) failed: {type(e).__name__}\n\n"
                f"Falling back to concatenated worker responses:\n\n"
                f"{concatenated}"
            )
            logger.warning(
                "Arbiter %s failed; returning concatenated workers: %s", arbiter, e
            )

    return ConsensusResponse(
        synthesized_response=synthesis,
        arbiter_model=arbiter,
        arbiter_failed=arbiter_error,
        execution_time_ms=int((time.monotonic() - start) * 1000),
        successful_workers=[w.model for w in successful],
        failed_workers=failed,
        raw_worker_responses=successful,
    )
