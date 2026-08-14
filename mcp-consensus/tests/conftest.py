import pytest


@pytest.fixture(autouse=True)
def _patch_litellm(monkeypatch):
    monkeypatch.setattr("mcp_consensus.consensus.LITELLM_URL", "http://litellm-test:4000")
    monkeypatch.setattr("mcp_consensus.consensus.LITELLM_KEY", "test-key")
    monkeypatch.setattr("mcp_consensus.api.LITELLM_URL", "http://litellm-test:4000")
    monkeypatch.setattr("mcp_consensus.api.LITELLM_KEY", "test-key")
