# MCP Consensus Server

MCP server that implements the **arbiter/worker pattern** for multi-model AI consensus. Integrates with Crush (or any MCP-compatible agent) via stdio transport.

## How It Works

```
Crush calls tool (e.g. multi_ai_review)
        │
        ▼
  ┌─────────────┐
  │ MCP Server   │
  │              │
  │  Fan out to  │──→ Worker 1 (gemini-3.5-flash)  ──┐
  │  N models    │──→ Worker 2 (llama-3.3-70b)      ──┤
  │  in parallel │──→ Worker 3 (mistral-small)       ──┤
  │              │──→ Worker 4 (codestral)           ──┤
  │              │──→ Worker N (...)                  ──┤
  │              │                                     │
  │  Arbiter     │◀── All responses ───────────────────┘
  │  synthesizes │
  └──────┬──────┘
         │
         ▼
  Consensus response back to Crush
```

## Tools

| Tool | Purpose |
|---|---|
| `multi_ai_design` | Multi-model consensus on architecture/design decisions |
| `multi_ai_review` | Multi-model code review with synthesized findings |
| `multi_ai_implement` | Multi-model implementation suggestions |

All tools share the same parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | (required) | The question, code, or task |
| `worker_models` | string[] | all available | Override which models to query |
| `arbiter_model` | string | gemini-3.5-flash | Override the synthesis model |
| `temperature` | float | 0.3 | Worker temperature |
| `timeout_seconds` | int | 60 | Per-worker timeout |
| `dry_run` | bool | false | Return prompts without calling models |

## Install

```bash
cd mcp-consensus
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configure Crush

Add to `.crushrc` or `~/.config/crush/crushrc`:

```
mcp add consensus -- python -m mcp_consensus
```

Or if using a venv:

```
mcp add consensus -- /path/to/mcp-consensus/.venv/bin/python -m mcp_consensus
```

### Environment Variables

Set these before starting Crush (or in `.crushrc`):

```bash
export LITELLM_URL=http://localhost:4000
export LITELLM_MASTER_KEY=sk-litellm-local
export DEFAULT_ARBITER=gemini-3.5-flash
```

## Test Standalone

```bash
# Verify it starts (Ctrl+C to stop)
python -m mcp_consensus

# Or test with mcp CLI
mcp dev mcp_consensus/server.py
```

## Requirements

- Python 3.11+
- LiteLLM proxy running (see [litellm-setup.md](../litellm-setup.md))
- At least one free AI model configured in LiteLLM
