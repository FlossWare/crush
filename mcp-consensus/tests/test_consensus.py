import asyncio
import json

import httpx
import pytest
import respx

from mcp_consensus.consensus import (
    _is_retryable,
    _parse_int_env,
    _resolve_workers,
    call_worker,
    run_consensus,
)
from mcp_consensus.models import (
    ConsensusRequest,
    ConsensusResponse,
    DEFAULT_WORKERS,
    FailedWorker,
    WorkerResponse,
)


LITELLM_BASE = "http://litellm-test:4000"

CHAT_URL = f"{LITELLM_BASE}/v1/chat/completions"


def _chat_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


# --- Config validation ---


class TestParseIntEnv:
    def test_valid(self, monkeypatch):
        monkeypatch.setenv("TEST_VAL", "5")
        assert _parse_int_env("TEST_VAL", 10, 1, 50) == 5

    def test_default(self, monkeypatch):
        monkeypatch.delenv("TEST_VAL", raising=False)
        assert _parse_int_env("TEST_VAL", 10, 1, 50) == 10

    def test_invalid_non_numeric(self, monkeypatch):
        monkeypatch.setenv("TEST_VAL", "abc")
        with pytest.raises(SystemExit, match="not a valid integer"):
            _parse_int_env("TEST_VAL", 10, 1, 50)

    def test_below_min(self, monkeypatch):
        monkeypatch.setenv("TEST_VAL", "0")
        with pytest.raises(SystemExit, match="must be between"):
            _parse_int_env("TEST_VAL", 10, 1, 50)

    def test_above_max(self, monkeypatch):
        monkeypatch.setenv("TEST_VAL", "100")
        with pytest.raises(SystemExit, match="must be between"):
            _parse_int_env("TEST_VAL", 10, 1, 50)

    def test_negative_rejected(self, monkeypatch):
        monkeypatch.setenv("TEST_VAL", "-1")
        with pytest.raises(SystemExit, match="must be between"):
            _parse_int_env("TEST_VAL", 10, 1, 50)

    def test_zero_rejected_when_min_is_one(self, monkeypatch):
        monkeypatch.setenv("TEST_VAL", "0")
        with pytest.raises(SystemExit, match="must be between"):
            _parse_int_env("TEST_VAL", 10, 1, 50)

    def test_empty_string_rejected(self, monkeypatch):
        monkeypatch.setenv("TEST_VAL", "")
        with pytest.raises(SystemExit, match="not a valid integer"):
            _parse_int_env("TEST_VAL", 10, 1, 50)


# --- Retry logic ---


class TestIsRetryable:
    def test_timeout_is_retryable(self):
        assert _is_retryable(asyncio.TimeoutError()) is True

    def test_5xx_is_retryable(self):
        resp = httpx.Response(500, request=httpx.Request("POST", CHAT_URL))
        assert _is_retryable(httpx.HTTPStatusError("", request=resp.request, response=resp)) is True

    def test_503_is_retryable(self):
        resp = httpx.Response(503, request=httpx.Request("POST", CHAT_URL))
        assert _is_retryable(httpx.HTTPStatusError("", request=resp.request, response=resp)) is True

    def test_4xx_is_not_retryable(self):
        resp = httpx.Response(404, request=httpx.Request("POST", CHAT_URL))
        assert _is_retryable(httpx.HTTPStatusError("", request=resp.request, response=resp)) is False

    def test_401_is_not_retryable(self):
        resp = httpx.Response(401, request=httpx.Request("POST", CHAT_URL))
        assert _is_retryable(httpx.HTTPStatusError("", request=resp.request, response=resp)) is False

    def test_429_is_retryable(self):
        resp = httpx.Response(429, request=httpx.Request("POST", CHAT_URL))
        assert _is_retryable(httpx.HTTPStatusError("", request=resp.request, response=resp)) is True

    def test_400_is_not_retryable(self):
        resp = httpx.Response(400, request=httpx.Request("POST", CHAT_URL))
        assert _is_retryable(httpx.HTTPStatusError("", request=resp.request, response=resp)) is False

    def test_connect_error_is_retryable(self):
        assert _is_retryable(httpx.ConnectError("refused")) is True

    def test_read_timeout_is_retryable(self):
        assert _is_retryable(httpx.ReadTimeout("timeout")) is True

    def test_generic_exception_is_not_retryable(self):
        assert _is_retryable(ValueError("bad")) is False


# --- Worker fleet resolution ---


class TestResolveWorkers:
    def test_explicit_workers(self):
        req = ConsensusRequest(prompt="test", worker_models=["model-a", "model-b"])
        assert _resolve_workers(req) == ["model-a", "model-b"]

    def test_empty_list_returns_empty(self):
        req = ConsensusRequest(prompt="test", worker_models=[])
        assert _resolve_workers(req) == []

    def test_none_uses_configured(self):
        req = ConsensusRequest(prompt="test")
        result = _resolve_workers(req)
        assert result == list(DEFAULT_WORKERS)

    def test_none_and_empty_are_distinct(self):
        none_req = ConsensusRequest(prompt="test", worker_models=None)
        empty_req = ConsensusRequest(prompt="test", worker_models=[])
        assert _resolve_workers(none_req) == list(DEFAULT_WORKERS)
        assert _resolve_workers(empty_req) == []


# --- Dry run ---


@pytest.mark.asyncio
class TestDryRun:
    async def test_dry_run_no_network_calls(self):
        req = ConsensusRequest(prompt="What is 2+2?", dry_run=True)
        with respx.mock(assert_all_called=False) as mock:
            mock.route(host="litellm-test").side_effect = AssertionError("Should not make network calls")
            result = await run_consensus("multi_ai_design", req)
        assert "DRY RUN" in result.synthesized_response
        assert result.execution_time_ms == 0
        assert result.successful_workers == []
        assert result.failed_workers == []

    async def test_dry_run_with_explicit_workers(self):
        req = ConsensusRequest(
            prompt="test", dry_run=True,
            worker_models=["custom-a", "custom-b"],
        )
        result = await run_consensus("multi_ai_review", req)
        assert "custom-a" in result.synthesized_response
        assert "custom-b" in result.synthesized_response
        assert "Workers (2)" in result.synthesized_response

    async def test_dry_run_without_workers_uses_default(self):
        req = ConsensusRequest(prompt="test", dry_run=True)
        result = await run_consensus("multi_ai_design", req)
        for model in DEFAULT_WORKERS:
            assert model in result.synthesized_response

    async def test_dry_run_with_none_workers_no_network(self):
        req = ConsensusRequest(prompt="test", dry_run=True, worker_models=None)
        with respx.mock(assert_all_called=False) as mock:
            mock.route(host="litellm-test").side_effect = AssertionError("No network calls in dry_run")
            result = await run_consensus("multi_ai_design", req)
        assert "DRY RUN" in result.synthesized_response
        assert len(result.successful_workers) == 0


# --- Worker selection ---


@pytest.mark.asyncio
class TestWorkerSelection:
    @respx.mock
    async def test_explicit_workers(self):
        respx.post(CHAT_URL).respond(json=_chat_response("worker output"))
        req = ConsensusRequest(prompt="test", worker_models=["model-x"])
        result = await run_consensus("multi_ai_design", req)
        assert "model-x" in result.successful_workers

    @respx.mock
    async def test_default_workers(self):
        respx.post(CHAT_URL).respond(json=_chat_response("response"))
        req = ConsensusRequest(prompt="test")
        result = await run_consensus("multi_ai_design", req)
        assert len(result.successful_workers) == len(DEFAULT_WORKERS)

    async def test_empty_workers_raises(self):
        req = ConsensusRequest(prompt="test", worker_models=[])
        with pytest.raises(ValueError, match="No worker models"):
            await run_consensus("multi_ai_design", req)


# --- Timeout and failure scenarios ---


@pytest.mark.asyncio
class TestWorkerFailure:
    @respx.mock
    async def test_worker_timeout(self, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 0)

        async def slow_response(request):
            await asyncio.sleep(10)
            return httpx.Response(200, json=_chat_response("late"))

        respx.post(CHAT_URL).mock(side_effect=slow_response)

        req = ConsensusRequest(prompt="test", worker_models=["slow-model"], timeout_seconds=5)
        result = await run_consensus("multi_ai_design", req)
        assert len(result.failed_workers) == 1
        assert result.failed_workers[0].model == "slow-model"

    @respx.mock
    async def test_partial_failure(self, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 0)

        def route_handler(request):
            body = json.loads(request.content)
            if body["model"] == "bad-model":
                return httpx.Response(500, text="Internal Server Error")
            return httpx.Response(200, json=_chat_response("good output"))

        respx.post(CHAT_URL).mock(side_effect=route_handler)

        req = ConsensusRequest(
            prompt="test",
            worker_models=["good-model", "bad-model"],
        )
        result = await run_consensus("multi_ai_design", req)
        assert len(result.successful_workers) == 1
        assert "good-model" in result.successful_workers
        assert len(result.failed_workers) == 1
        assert result.failed_workers[0].model == "bad-model"

    @respx.mock
    async def test_all_workers_fail(self, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 0)
        respx.post(CHAT_URL).respond(status_code=500)

        req = ConsensusRequest(prompt="test", worker_models=["m1", "m2"])
        result = await run_consensus("multi_ai_design", req)
        assert "All 2 workers failed" in result.synthesized_response
        assert len(result.failed_workers) == 2
        assert result.successful_workers == []

    @respx.mock
    async def test_arbiter_failure_fallback(self, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 0)
        call_count = 0

        def route_handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=_chat_response("worker response"))
            return httpx.Response(500, text="arbiter down")

        respx.post(CHAT_URL).mock(side_effect=route_handler)

        req = ConsensusRequest(
            prompt="test",
            worker_models=["w1"],
            arbiter_model="bad-arbiter",
        )
        result = await run_consensus("multi_ai_design", req)
        assert result.arbiter_failed is True
        assert "failed" in result.synthesized_response.lower() or "Arbiter" in result.synthesized_response
        assert result.successful_workers == ["w1"]
        assert len(result.raw_worker_responses) == 1
        assert result.raw_worker_responses[0].response == "worker response"

    @respx.mock
    async def test_non_retryable_error_fails_immediately(self, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 3)
        call_count = 0

        def route_handler(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(404, text="Not Found")

        respx.post(CHAT_URL).mock(side_effect=route_handler)

        req = ConsensusRequest(prompt="test", worker_models=["m1"])
        result = await run_consensus("multi_ai_design", req)
        assert len(result.failed_workers) == 1
        assert "404" in result.failed_workers[0].error
        assert call_count == 1  # no retries for 4xx

    @respx.mock
    async def test_transient_failure_retries_then_succeeds(self, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 2)
        call_count = 0

        def route_handler(request):
            nonlocal call_count
            call_count += 1
            body = json.loads(request.content)
            if body["model"] == "flaky-worker":
                if call_count <= 2:
                    return httpx.Response(500, text="Server Error")
                return httpx.Response(200, json=_chat_response("succeeded on retry"))
            return httpx.Response(200, json=_chat_response("arbiter synthesis"))

        respx.post(CHAT_URL).mock(side_effect=route_handler)

        req = ConsensusRequest(prompt="test", worker_models=["flaky-worker"])
        result = await run_consensus("multi_ai_design", req)
        assert "flaky-worker" in result.successful_workers
        assert call_count >= 3  # 2 failures + 1 success + arbiter


# --- Timeout semantics ---


@pytest.mark.asyncio
class TestTimeoutSemantics:
    @respx.mock
    async def test_total_deadline_not_per_attempt(self, monkeypatch):
        """Retries share the total deadline — a 5s deadline with 2 retries
        does NOT allow 3 × 5s = 15s of wall-clock time."""
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 2)

        async def slow_response(request):
            await asyncio.sleep(10)
            return httpx.Response(200, json=_chat_response("late"))

        respx.post(CHAT_URL).mock(side_effect=slow_response)

        req = ConsensusRequest(prompt="test", worker_models=["slow"], timeout_seconds=5)
        start = asyncio.get_event_loop().time()
        result = await run_consensus("multi_ai_design", req)
        elapsed = asyncio.get_event_loop().time() - start
        assert len(result.failed_workers) == 1
        assert elapsed < 8  # well under 3 × 5 = 15s

    @respx.mock
    async def test_separate_arbiter_timeout(self, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 0)
        call_count = 0

        async def route_handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=_chat_response("worker ok"))
            await asyncio.sleep(15)
            return httpx.Response(200, json=_chat_response("arbiter ok"))

        respx.post(CHAT_URL).mock(side_effect=route_handler)

        req = ConsensusRequest(
            prompt="test",
            worker_models=["w1"],
            timeout_seconds=30,
            arbiter_timeout_seconds=5,
        )
        result = await run_consensus("multi_ai_design", req)
        assert result.arbiter_failed is True
        assert "failed" in result.synthesized_response.lower() or "Arbiter" in result.synthesized_response

    @respx.mock
    async def test_arbiter_temperature_separate(self, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 0)
        temperatures = []

        def route_handler(request):
            body = json.loads(request.content)
            temperatures.append(body["temperature"])
            return httpx.Response(200, json=_chat_response("output"))

        respx.post(CHAT_URL).mock(side_effect=route_handler)

        req = ConsensusRequest(
            prompt="test",
            worker_models=["w1"],
            temperature=0.7,
            arbiter_temperature=0.1,
        )
        await run_consensus("multi_ai_design", req)
        assert temperatures[0] == 0.7
        assert temperatures[1] == 0.1


# --- Concurrency limits ---


@pytest.mark.asyncio
class TestConcurrencyLimits:
    @respx.mock
    async def test_semaphore_limits_concurrency(self, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 0)
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def tracked_post(request):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return httpx.Response(200, json=_chat_response("ok"))

        respx.post(CHAT_URL).mock(side_effect=tracked_post)

        monkeypatch.setattr("mcp_consensus.consensus.MAX_CONCURRENT_WORKERS", 2)

        workers = [f"model-{i}" for i in range(5)]
        req = ConsensusRequest(prompt="test", worker_models=workers)
        result = await run_consensus("multi_ai_design", req)
        assert max_concurrent <= 2


# --- MCP tool registration (basic checks; protocol tests in test_mcp_protocol.py) ---


class TestMCPToolRegistration:
    def test_tools_are_defined(self):
        from mcp_consensus.server import TOOLS, VALID_TOOLS
        assert len(TOOLS) == 3
        names = {t.name for t in TOOLS}
        assert names == {"multi_ai_design", "multi_ai_review", "multi_ai_implement"}
        assert VALID_TOOLS == names

    def test_input_schema_has_prompt(self):
        from mcp_consensus.server import INPUT_SCHEMA
        assert "prompt" in INPUT_SCHEMA.get("properties", {})
        assert "prompt" in INPUT_SCHEMA.get("required", [])

    def test_handlers_registered(self):
        from mcp_consensus.server import app
        assert app.get_request_handler("tools/list") is not None
        assert app.get_request_handler("tools/call") is not None
