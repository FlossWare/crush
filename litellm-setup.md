# Setup Crush + LiteLLM (Free API Round-Robin)

## Overview

This sets up:
1. **LiteLLM proxy** — round-robins requests across multiple free API keys per provider
2. **Crush** (Charm's terminal coding agent) on any machine, routing all requests through LiteLLM

All models are FREE — no paid API usage.

---

## Step 1: Install LiteLLM

### Create venv and install

```bash
python3 -m venv ~/litellm-venv
source ~/litellm-venv/bin/activate
pip install 'litellm[proxy]'
pip install 'fastapi<0.116.0'   # Pin — newer versions break litellm imports
```

### Create config (`~/litellm-config.yaml`)

Define each model with multiple API keys. LiteLLM round-robins across entries with the same `model_name`.

The pattern: repeat the same `model_name` block for each API key you have, varying only `api_key` and `model_info.id`.

```yaml
model_list:
  # Google Gemini — example with 3 keys
  - model_name: gemini-3.5-flash
    litellm_params:
      model: gemini/gemini-3.5-flash
      api_key: os.environ/GOOGLE_API_KEY
    model_info:
      id: gemini-flash-1
  - model_name: gemini-3.5-flash
    litellm_params:
      model: gemini/gemini-3.5-flash
      api_key: os.environ/GOOGLE_API_KEY_2
    model_info:
      id: gemini-flash-2
  - model_name: gemini-3.5-flash
    litellm_params:
      model: gemini/gemini-3.5-flash
      api_key: os.environ/GOOGLE_API_KEY_3
    model_info:
      id: gemini-flash-3

  # Groq
  - model_name: llama-3.3-70b
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: os.environ/GROQ_API_KEY
    model_info:
      id: groq-llama-1
  - model_name: llama-3.3-70b
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: os.environ/GROQ_API_KEY_2
    model_info:
      id: groq-llama-2

  # Mistral — example with 4 keys
  - model_name: mistral-small
    litellm_params:
      model: mistral/mistral-small-latest
      api_key: os.environ/MISTRAL_API_KEY
    model_info:
      id: mistral-small-1
  - model_name: mistral-small
    litellm_params:
      model: mistral/mistral-small-latest
      api_key: os.environ/MISTRAL_API_KEY_2
    model_info:
      id: mistral-small-2
  # ... repeat for additional keys

  - model_name: codestral
    litellm_params:
      model: mistral/codestral-latest
      api_key: os.environ/MISTRAL_API_KEY
    model_info:
      id: codestral-1
  # ... repeat for additional keys

  # Cerebras
  - model_name: cerebras-llama
    litellm_params:
      model: cerebras/llama-3.3-70b
      api_key: os.environ/CEREBRAS_API_KEY
    model_info:
      id: cerebras-llama-1
  # ... repeat for additional keys

  # OpenRouter — free models only (note the :free suffix)
  - model_name: nemotron-ultra
    litellm_params:
      model: openrouter/nvidia/nemotron-3-ultra-550b-a55b:free
      api_key: os.environ/OPENROUTER_API_KEY
    model_info:
      id: or-nemotron-ultra-1
  # ... repeat for additional keys

  - model_name: gemma-4-31b
    litellm_params:
      model: openrouter/google/gemma-4-31b-it:free
      api_key: os.environ/OPENROUTER_API_KEY
    model_info:
      id: or-gemma-1
  # ... repeat for additional keys

  # Pollinations
  - model_name: pollinations
    litellm_params:
      model: openai/openai-fast
      api_base: https://text.pollinations.ai/openai
      api_key: os.environ/POLLINATIONS_API_KEY
    model_info:
      id: pollinations-1

  # Cloudflare Workers AI (daily free limit resets)
  - model_name: cloudflare
    litellm_params:
      model: openai/@cf/meta/llama-3.3-70b-instruct-fp8-fast
      api_base: https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/v1
      api_key: os.environ/CLOUDFLARE_API_KEY
    model_info:
      id: cf-1
  # ... repeat for additional keys

litellm_settings:
  num_retries: 3
  request_timeout: 60
  fallbacks:
    - gemini-3.5-flash:
      - llama-3.3-70b
      - mistral-small
      - cerebras-llama
    - llama-3.3-70b:
      - gemini-3.5-flash
      - mistral-small
    - mistral-small:
      - gemini-3.5-flash
      - llama-3.3-70b
  set_verbose: false
  drop_params: true

router_settings:
  routing_strategy: simple-shuffle
  allowed_fails: 3
  cooldown_time: 30
  retry_after: 5

general_settings:
  master_key: sk-litellm-local
  database_url: null
```

### Create env file for systemd

Extract API key env vars into a file systemd can load:

```bash
grep "^export " ~/.bashrc | grep "=" | sed "s/^export //" | sed "s/['\"]//g" | grep -v "^PATH=" > ~/.litellm.env
chmod 600 ~/.litellm.env
```

### Create systemd service

```ini
# /etc/systemd/system/litellm.service
[Unit]
Description=LiteLLM Proxy - Free API Round-Robin
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=%u
Group=%u
WorkingDirectory=%h
EnvironmentFile=%h/.litellm.env
ExecStart=%h/litellm-venv/bin/litellm --config %h/litellm-config.yaml --host 0.0.0.0 --port 4000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

> **Note:** Replace `%u` and `%h` with your actual username and home directory if your systemd version doesn't expand them, e.g. `User=myuser`, `WorkingDirectory=/home/myuser`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable litellm
sudo systemctl start litellm
# Takes ~50s to start (heavy Python imports)
```

### Verify

```bash
curl http://localhost:4000/v1/models -H "Authorization: Bearer sk-litellm-local"
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-litellm-local" \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.5-flash","messages":[{"role":"user","content":"hello"}],"max_tokens":50}'
```

---

## Step 2: Install Crush

### From Charm's RPM repo (Fedora/RHEL)

```bash
sudo dnf install crush
```

### From GitHub releases (Linux ARM64 / Termux)

```bash
curl -sL "https://github.com/charmbracelet/crush/releases/latest/download/crush_Linux_arm64.tar.gz" -o crush.tar.gz
tar xzf crush.tar.gz
mv crush /usr/local/bin/  # or $PREFIX/bin on Termux
```

### From GitHub releases (Linux x86_64)

```bash
curl -sL "https://github.com/charmbracelet/crush/releases/latest/download/crush_Linux_x86_64.tar.gz" -o crush.tar.gz
tar xzf crush.tar.gz
sudo mv crush /usr/local/bin/
```

---

## Step 3: Configure Crush

Crush has TWO config locations that MUST be consistent:
1. **Config file:** `~/.config/crush/crush.json` — provider/model definitions
2. **State file:** `~/.local/share/crush/crush.json` — cached model selections

If the state file has stale model selections, crush ignores the config and uses the cached models.

### Config file (`~/.config/crush/crush.json`)

```json
{
  "$schema": "https://charm.land/crush.json",
  "providers": {
    "litellm": {
      "type": "openai-compat",
      "base_url": "http://LITELLM_HOST:4000/v1",
      "api_key": "sk-litellm-local",
      "flat_rate": true,
      "discover_models": false,
      "models": [
        { "id": "gemini-3.5-flash", "name": "Gemini 3.5 Flash" },
        { "id": "gemini-3.5-pro", "name": "Gemini 3.5 Pro" },
        { "id": "llama-3.3-70b", "name": "Llama 3.3 70B (Groq)" },
        { "id": "mistral-small", "name": "Mistral Small" },
        { "id": "codestral", "name": "Codestral" },
        { "id": "cerebras-llama", "name": "Cerebras Llama" },
        { "id": "nemotron-ultra", "name": "Nemotron Ultra (OpenRouter)" },
        { "id": "gemma-4-31b", "name": "Gemma 4 31B (OpenRouter)" },
        { "id": "pollinations", "name": "Pollinations" },
        { "id": "cloudflare", "name": "Cloudflare Workers AI" }
      ]
    },
    "anthropic": { "disable": true },
    "openai": { "disable": true },
    "deepseek": { "disable": true },
    "cohere": { "disable": true },
    "xai": { "disable": true },
    "azure": { "disable": true },
    "bedrock": { "disable": true },
    "bedrock-europe": { "disable": true },
    "copilot": { "disable": true },
    "vercel": { "disable": true },
    "vertexai": { "disable": true }
  },
  "models": {
    "default": {
      "model": "gemini-3.5-flash",
      "provider": "litellm"
    },
    "large": {
      "model": "gemini-3.5-flash",
      "provider": "litellm"
    },
    "small": {
      "model": "mistral-small",
      "provider": "litellm"
    }
  }
}
```

Replace `LITELLM_HOST` with:
- `localhost` — if LiteLLM runs locally or you have an SSH tunnel
- The LAN IP of the machine running LiteLLM (or the tunnel)

### State file (`~/.local/share/crush/crush.json`)

MUST match the config. Write this on first setup or whenever you change models:

```json
{"models":{"default":{"model":"gemini-3.5-flash","provider":"litellm","max_tokens":1048576},"small":{"model":"mistral-small","provider":"litellm","max_tokens":32768},"large":{"model":"gemini-3.5-flash","provider":"litellm","max_tokens":1048576}},"recent_models":{"default":[{"model":"gemini-3.5-flash","provider":"litellm"}],"small":[{"model":"mistral-small","provider":"litellm"}],"large":[{"model":"gemini-3.5-flash","provider":"litellm"}]}}
```

### Disable paid providers in cache

Crush auto-populates `~/.local/share/crush/providers.json` with 40+ built-in providers on every run. You cannot prevent this, but the `"disable": true` entries in the config prevent crush from using them.

### Verify

```bash
crush run "Say hello"
# Check logs to confirm it used litellm
cat ~/.crush/logs/crush.log | grep "ModelProvider"
# Should show: provider=litellm model=gemini-3.5-flash
```

---

## Troubleshooting

### Crush ignores config and uses OpenAI/paid models

Crush caches model selections in `~/.local/share/crush/crush.json`. If this file has stale entries (e.g., `gpt-5.6-sol` via `openai`), crush uses those instead of the config.

**Fix:** Overwrite the state file (see Step 3 above).

### Crush says "model not available" or "Vertex_ai_betaException"

Some Google API keys may not have access to older Gemini model names (e.g., `gemini-2.5-flash` deprecated on newer accounts). Check which models your key supports:

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY" | python3 -c "
import json,sys
for m in json.load(sys.stdin).get('models',[]):
    if 'gemini' in m['name'] and ('flash' in m['name'] or 'pro' in m['name']):
        print(m['name'])
"
```

### LiteLLM won't start — FastAPI import error

```
ImportError: cannot import name 'get_flat_dependant' from 'fastapi.dependencies.utils'
```

**Fix:** Pin FastAPI: `pip install "fastapi<0.116.0"`

### LiteLLM startup takes 50+ seconds

Normal — heavy Python imports. The systemd service handles this automatically.

### Cerebras rate limits (429)

Cerebras has aggressive TPM limits on free tier. Crush's system prompt is ~14K tokens which can exhaust the limit in one request. Use Gemini as default, Cerebras as fallback only.

---

## Architecture Summary

```
        ┌─────────────────────┐
        │  LiteLLM :4000      │
        │  (systemd service)  │
        │                     │
        │  Round-robins across │
        │  N free API keys per │
        │  provider:           │
        │  - Google Gemini     │
        │  - Groq              │
        │  - Mistral           │
        │  - Cerebras          │
        │  - OpenRouter (free) │
        │  - Pollinations      │
        │  - Cloudflare        │
        └────────┬────────────┘
                 │ LAN
        ┌────────┴────────────┐
        │  Crush clients      │
        │  → LiteLLM_HOST:4000│
        └─────────────────────┘
```

---

## Adding a New Machine

1. Install Crush (RPM or GitHub release)
2. Create `~/.config/crush/crush.json` — set `LITELLM_HOST` to the appropriate address
3. Write the state file at `~/.local/share/crush/crush.json`
4. Export API key env vars in `~/.bashrc`
5. Test: `crush run "hello"`
6. Verify: `grep ModelProvider ~/.crush/logs/crush.log`

## Adding a New API Key

1. Add the env var to `~/.bashrc` on the LiteLLM server
2. Regenerate the env file: `grep "^export " ~/.bashrc | grep "=" | sed "s/^export //" | sed "s/['\"]//g" | grep -v "^PATH=" > ~/.litellm.env`
3. Add a new entry in `~/litellm-config.yaml` with the same `model_name` and a unique `model_info.id`
4. Restart: `sudo systemctl restart litellm`

## Adding a New Provider

1. Add entries to `litellm-config.yaml` using litellm's provider prefix (e.g., `groq/`, `mistral/`, `gemini/`, `openrouter/`)
2. Add fallback rules in `litellm_settings.fallbacks`
3. Add the model to crush's config `models` array in the `litellm` provider
4. Restart litellm, update crush state files on all machines
