# MCP Consensus Server

MCP server and REST API implementing the **arbiter/worker pattern** for multi-model AI analysis. Each tool fans out a prompt to N free AI models in parallel, then an arbiter model synthesizes their independent responses into a single definitive answer.

> **Note:** This is independent worker analysis followed by arbiter synthesis, not voting or weighted consensus. Each worker generates its response independently; the arbiter resolves conflicts and produces a unified output. Weighted consensus, adversarial verification, and scoring are planned for future iterations.

## How It Works

```
Client calls tool (e.g. multi_ai_review)
        │
        ▼
  ┌─────────────┐
  │ MCP Server   │  or REST API (/v1/consensus)
  │              │
  │  Fan out to  │──→ Worker 1 (gemini-3.5-flash)  ──┐
  │  N workers   │──→ Worker 2 (llama-3.3-70b)      ──┤
  │  in parallel │──→ Worker 3 (mistral-small)       ──┤
  │              │──→ Worker 4 (codestral)           ──┤
  │              │──→ Worker N (...)                  ──┤
  │              │                                     │
  │  Arbiter     │◀── All responses ───────────────────┘
  │  synthesizes │
  └──────┬──────┘
         │
         ▼
  Synthesized response back to client
```

## Transports

| Transport | Protocol | Entrypoint |
|---|---|---|
| MCP (stdio) | JSON-RPC over stdin/stdout | `mcp-consensus` |
| REST API | HTTP/JSON | `mcp-consensus-api` |

Both transports share the same consensus engine (`consensus.py`).

## Tools

| Tool | Purpose |
|---|---|
| `multi_ai_design` | Multi-model analysis of architecture/design decisions |
| `multi_ai_review` | Multi-model code review with synthesized findings |
| `multi_ai_implement` | Multi-model implementation suggestions |

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | *(required)* | The question, code, or task (max 100,000 characters) |
| `worker_models` | string[] | configured fleet | Override which models to query. `null` uses the configured fleet. An empty list is invalid and returns an error (including in dry-run). |
| `arbiter_model` | string | gemini-3.5-flash | Override the synthesis model |
| `temperature` | float | 0.3 | Worker model temperature (0.0–1.0) |
| `arbiter_temperature` | float | 0.3 | Arbiter synthesis temperature (0.0–1.0). Independent of worker temperature. |
| `timeout_seconds` | int | 60 | Total worker deadline in seconds (5–300). Covers all attempts including retries. |
| `arbiter_timeout_seconds` | int | timeout_seconds | Arbiter timeout in seconds (5–600). Defaults to the worker timeout if not set. |
| `dry_run` | bool | false | Return prompts without making any network calls |

## Install

```bash
cd mcp-consensus
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# For running tests:
pip install -e ".[test]"
```

## Configure the Worker Fleet

The worker fleet determines which models participate in each consensus call. Models are resolved in this order:

1. **Explicit `worker_models` parameter** — per-request override
2. **`WORKER_FLEET` environment variable** — comma-separated model list
3. **`DEFAULT_WORKERS` in `models.py`** — built-in fallback

```bash
# Set a custom fleet via environment
export WORKER_FLEET="gemini-3.5-flash,llama-3.3-70b,mistral-small"
```

LiteLLM provides model routing and API key management. The worker fleet controls *which* models participate — LiteLLM handles *how* to reach them.

## Configure Crush (MCP transport)

Add to `.crushrc` or `~/.config/crush/crushrc`:

```
mcp add consensus -- python -m mcp_consensus
```

Or if using a venv:

```
mcp add consensus -- /path/to/mcp-consensus/.venv/bin/python -m mcp_consensus
```

## REST API

Start the REST API server:

```bash
mcp-consensus-api
# or
python -m mcp_consensus.api
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (verifies LiteLLM connectivity). Always unauthenticated. |
| GET | `/v1/models` | List available models from LiteLLM |
| POST | `/v1/consensus` | Run a consensus call |

### Authentication

By default the REST API binds to `127.0.0.1` and does not require a key (convenient for local use).

Set `API_KEY` to require authentication on `/v1/*`:

```bash
export API_KEY="change-me"
```

Clients must send either:

- `X-API-Key: <key>`, or
- `Authorization: Bearer <key>`

`/health` stays open for probes and reports `auth_required: true|false`.

### Example

```bash
curl -X POST http://localhost:8080/v1/consensus \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "tool": "review",
    "prompt": "Review this function for bugs...",
    "worker_models": ["gemini-3.5-flash", "llama-3.3-70b"],
    "temperature": 0.3,
    "arbiter_temperature": 0.1
  }'
```

The REST API binds to `127.0.0.1:8080` by default. Set `API_HOST` and `API_PORT` to change this. Invalid `API_PORT` values produce a clear configuration error at startup.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LITELLM_URL` | `http://localhost:4000` | LiteLLM proxy URL |
| `LITELLM_MASTER_KEY` | *(empty)* | LiteLLM API key (omit if no auth) |
| `DEFAULT_ARBITER` | `gemini-3.5-flash` | Default arbiter model |
| `WORKER_FLEET` | *(uses DEFAULT_WORKERS)* | Comma-separated list of worker models |
| `MAX_CONCURRENT_WORKERS` | `10` | Max parallel worker calls (1–50) |
| `WORKER_RETRIES` | `2` | Retry count for transient worker failures (0–10) |
| `API_HOST` | `127.0.0.1` | REST API bind address |
| `API_PORT` | `8080` | REST API port (1–65535) |
| `API_KEY` | *(empty)* | Optional REST shared secret; when set, `/v1/*` requires `X-API-Key` or Bearer |

Invalid values for `MAX_CONCURRENT_WORKERS`, `WORKER_RETRIES`, or `API_PORT` produce a clear configuration error at startup.

## Testing

```bash
pip install -e ".[test]"
pytest tests/ -v
```

Tests cover: dry-run, explicit/default worker selection, worker timeout, individual/partial/all-worker failure, arbiter failure fallback (concatenated workers in `synthesized_response`), concurrency limits, MCP tool registration, MCP protocol smoke path, REST API endpoints (including optional API key auth), retry logic, and timeout semantics.

## Requirements

- Python 3.11+
- LiteLLM proxy running (see [litellm-setup.md](../litellm-setup.md))
- At least one free AI model configured in LiteLLM

## Error Handling

- **Worker failures** are isolated — a failing worker doesn't affect others. Failed workers are reported with a **sanitized** error token (exception type / HTTP status), not raw exception messages. Full details are logged server-side only.
- **Transient errors** (5xx, timeouts, connection errors) are retried with exponential backoff within the total worker deadline. Client errors (4xx) fail immediately without retry.
- **Arbiter failure** sets `arbiter_failed=true` and puts a **concatenated dump of successful worker responses** into `synthesized_response` (prefixed with a short failure note using the exception type name only).
- **Empty worker fleet** (`worker_models: []` or no configured fleet) is always an error, including dry-run.
- **All-workers-fail** returns a descriptive error with per-worker sanitized failure tokens.
- **REST errors** toward clients use fixed messages (e.g. `LiteLLM unavailable`); upstream exception text is not returned in HTTP bodies.
