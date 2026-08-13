# Crush

Setup guides, scripts, and configuration for [Crush](https://github.com/charmbracelet/crush) (Charm's terminal coding agent).

## Quick Start

```bash
# 1. On the LiteLLM server (any machine with API keys exported in ~/.bashrc):
./scripts/setup-litellm.sh

# 2. On each machine that needs Crush:
./scripts/setup-crush.sh                              # Linux / macOS / Termux (Android)
.\scripts\setup-crush.ps1                              # Windows (PowerShell)

# 3. To add more API keys later:
./scripts/add-provider.sh gemini GOOGLE_API_KEY_3
```

## Guides

- [LiteLLM Setup](litellm-setup.md) — Round-robin proxy across multiple free API keys, with Crush as client
- [Free AI Providers](free-ai-providers.md) — All free model providers with signup links and LiteLLM prefixes

## Scripts

| Script | Platform | Purpose |
|---|---|---|
| [setup-litellm.sh](scripts/setup-litellm.sh) | Linux / macOS | Install LiteLLM proxy, auto-detect API keys, generate config, create systemd service |
| [setup-crush.sh](scripts/setup-crush.sh) | Linux / macOS / Android (Termux) | Install Crush, query LiteLLM for models, generate config |
| [setup-crush.ps1](scripts/setup-crush.ps1) | Windows (PowerShell) | Install Crush, query LiteLLM for models, generate config |
| [add-provider.sh](scripts/add-provider.sh) | Linux / macOS | Add a new API key to LiteLLM and restart |

## Platform Support

| Platform | LiteLLM Server | Crush Client |
|---|---|---|
| Linux (x86_64) | `setup-litellm.sh` | `setup-crush.sh` |
| Linux (arm64) | `setup-litellm.sh` | `setup-crush.sh` |
| macOS (Apple Silicon) | `setup-litellm.sh` | `setup-crush.sh` |
| macOS (Intel) | `setup-litellm.sh` | `setup-crush.sh` |
| Windows | Not supported | `setup-crush.ps1` |
| Android (Termux) | Not supported | `setup-crush.sh` |
| iOS (iSH / a-Shell) | Not supported | Manual install (see below) |

### iOS Notes

Crush does not publish iOS binaries. On jailbroken devices or terminal apps like iSH/a-Shell, you can point a compatible LLM client at your LiteLLM proxy — it's a standard OpenAI-compatible API at `http://LITELLM_HOST:4000/v1`.

## Environment Variables

Scripts use these env vars (all optional, with defaults):

| Variable | Default | Used By |
|---|---|---|
| `LITELLM_HOST` | `localhost` | setup-crush.sh |
| `LITELLM_PORT` | `4000` | Both |
| `LITELLM_MASTER_KEY` | `sk-litellm-local` | Both |
| `LITELLM_DIR` | `$HOME` | setup-litellm.sh |
| `DEFAULT_MODEL` | `gemini-3.5-flash` | setup-crush.sh |
| `SMALL_MODEL` | `mistral-small` | setup-crush.sh |
