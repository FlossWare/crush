import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from mcp_consensus.api import app


LITELLM_BASE = "http://litellm-test:4000"
CHAT_URL = f"{LITELLM_BASE}/v1/chat/completions"
MODELS_URL = f"{LITELLM_BASE}/v1/models"
HEALTH_URL = f"{LITELLM_BASE}/health/liveliness"


@pytest.fixture
def client():
    return TestClient(app)


def _chat_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


class TestHealthEndpoint:
    @respx.mock
    def test_healthy(self, client):
        respx.get(HEALTH_URL).respond(200)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["litellm"] == "connected"

    @respx.mock
    def test_degraded(self, client):
        respx.get(HEALTH_URL).respond(500)
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["litellm"] == "unreachable"


class TestModelsEndpoint:
    @respx.mock
    def test_list_models(self, client):
        respx.get(MODELS_URL).respond(json={
            "data": [
                {"id": "model-a"},
                {"id": "model-b"},
                {"id": "model-a"},
            ]
        })
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["models"] == ["model-a", "model-b"]
        assert data["count"] == 2

    @respx.mock
    def test_litellm_unavailable(self, client):
        respx.get(MODELS_URL).mock(side_effect=httpx.ConnectError("refused"))
        resp = client.get("/v1/models")
        assert resp.status_code == 502


class TestConsensusEndpoint:
    @respx.mock
    def test_dry_run(self, client):
        resp = client.post("/v1/consensus", json={
            "prompt": "test prompt",
            "dry_run": True,
            "tool": "design",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "DRY RUN" in data["synthesized_response"]

    @respx.mock
    def test_consensus_success(self, client, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 0)
        call_count = 0

        def route_handler(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=_chat_response(f"response {call_count}"))

        respx.post(CHAT_URL).mock(side_effect=route_handler)

        resp = client.post("/v1/consensus", json={
            "prompt": "test",
            "worker_models": ["m1"],
            "tool": "review",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["arbiter_model"]
        assert len(data["successful_workers"]) == 1

    def test_missing_prompt(self, client):
        resp = client.post("/v1/consensus", json={"tool": "design"})
        assert resp.status_code == 422

    def test_invalid_tool(self, client):
        resp = client.post("/v1/consensus", json={
            "prompt": "test",
            "tool": "nonexistent",
        })
        assert resp.status_code == 422

    def test_empty_workers_returns_422(self, client):
        resp = client.post("/v1/consensus", json={
            "prompt": "test",
            "worker_models": [],
            "tool": "design",
        })
        assert resp.status_code == 422
        assert "No worker models" in resp.json()["detail"]

    @respx.mock
    def test_new_fields_forwarded(self, client, monkeypatch):
        monkeypatch.setattr("mcp_consensus.consensus.WORKER_RETRIES", 0)
        temperatures = []

        def route_handler(request):
            body = json.loads(request.content)
            temperatures.append(body["temperature"])
            return httpx.Response(200, json=_chat_response("ok"))

        respx.post(CHAT_URL).mock(side_effect=route_handler)

        resp = client.post("/v1/consensus", json={
            "prompt": "test",
            "worker_models": ["w1"],
            "temperature": 0.8,
            "arbiter_temperature": 0.2,
            "timeout_seconds": 30,
            "arbiter_timeout_seconds": 60,
            "tool": "design",
        })
        assert resp.status_code == 200
        assert temperatures[0] == 0.8
        assert temperatures[1] == 0.2


class TestAPIDefaults:
    def test_binds_localhost_by_default(self):
        import os
        os.environ.pop("API_HOST", None)
        from mcp_consensus.api import main
        import inspect
        source = inspect.getsource(main)
        assert "127.0.0.1" in source
