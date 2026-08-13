# Setup Crush + LiteLLM (Free API Round-Robin)

## Overview

This sets up:
1. **LiteLLM proxy** on aio-01:4000 — round-robins requests across multiple free API keys per provider
2. **Crush** (Charm's terminal coding agent) on any machine, routing all requests through LiteLLM
3. **SSH tunnel** for machines that can't reach aio-01 directly (cabin network)

All models are FREE — no paid API usage.

---

## Step 1: Install LiteLLM on aio-01 (flossware user)

### Create venv and install

```bash
ssh aio-01
sudo -u flossware bash -c "
  cd /home/flossware
  python3 -m venv litellm-venv
  source litellm-venv/bin/activate
  pip install 'litellm[proxy]'
  pip install 'fastapi<0.116.0'   # Pin — newer versions break litellm imports
"
```

### Create config (`/home/flossware/litellm-config.yaml`)

Define each model with multiple API keys. LiteLLM round-robins across keys with the same `model_name`.

```yaml
model_list:
  # Google Gemini — 3 keys
  - model_name: gemini-3.5-flash
    litellm_params:
      model: gemini/gemini-3.5-flash
      api_key: os.environ/GOOGLE_API_KEY
    model_info:
      id: gemini-flash-base
  - model_name: gemini-3.5-flash
    litellm_params:
      model: gemini/gemini-3.5-flash
      api_key: os.environ/GOOGLE_API_KEY_FLOSSWARE
    model_info:
      id: gemini-flash-flossware
  - model_name: gemini-3.5-flash
    litellm_params:
      model: gemini/gemini-3.5-flash
      api_key: os.environ/GOOGLE_API_KEY_HOTMAIL
    model_info:
      id: gemini-flash-hotmail

  # Groq — 2 keys
  - model_name: llama-3.3-70b
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: os.environ/GROQ_API_KEY
    model_info:
      id: groq-llama-base
  - model_name: llama-3.3-70b
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: os.environ/GROQ_API_KEY_FLOSSWARE
    model_info:
      id: groq-llama-flossware

  # Mistral — 4 keys
  - model_name: mistral-small
    litellm_params:
      model: mistral/mistral-small-latest
      api_key: os.environ/MISTRAL_API_KEY
    model_info:
      id: mistral-small-base
  - model_name: mistral-small
    litellm_params:
      model: mistral/mistral-small-latest
      api_key: os.environ/MISTRAL_API_KEY_FLOSSWARE
    model_info:
      id: mistral-small-flossware
  - model_name: mistral-small
    litellm_params:
      model: mistral/mistral-small-latest
      api_key: os.environ/MISTRAL_API_KEY_HOTMAIL
    model_info:
      id: mistral-small-hotmail
  - model_name: mistral-small
    litellm_params:
      model: mistral/mistral-small-latest
      api_key: os.environ/MISTRAL_API_KEY_NCRR
    model_info:
      id: mistral-small-ncrr

  - model_name: codestral
    litellm_params:
      model: mistral/codestral-latest
      api_key: os.environ/MISTRAL_API_KEY
    model_info:
      id: codestral-base
  # ... repeat codestral for FLOSSWARE, HOTMAIL, NCRR keys

  # Cerebras — 4 keys
  - model_name: cerebras-llama
    litellm_params:
      model: cerebras/llama-3.3-70b
      api_key: os.environ/CEREBRAS_API_KEY
    model_info:
      id: cerebras-llama-base
  # ... repeat for FLOSSWARE, HOTMAIL, NCRR keys

  # OpenRouter — 4 keys, free models only
  - model_name: nemotron-ultra
    litellm_params:
      model: openrouter/nvidia/nemotron-3-ultra-550b-a55b:free
      api_key: os.environ/OPENROUTER_API_KEY
    model_info:
      id: or-nemotron-ultra-base
  # ... repeat for FLOSSWARE, HOTMAIL, NCRR keys

  - model_name: gemma-4-31b
    litellm_params:
      model: openrouter/google/gemma-4-31b-it:free
      api_key: os.environ/OPENROUTER_API_KEY
    model_info:
      id: or-gemma-base
  # ... repeat for FLOSSWARE, HOTMAIL, NCRR keys

  # Pollinations — 2 keys
  - model_name: pollinations
    litellm_params:
      model: openai/openai-fast
      api_base: https://text.pollinations.ai/openai
      api_key: os.environ/POLLINATIONS_API_KEY
    model_info:
      id: pollinations-base
  # ... repeat for FLOSSWARE key

  # Cloudflare Workers AI — 3 keys (daily limit resets)
  - model_name: cloudflare
    litellm_params:
      model: openai/@cf/meta/llama-3.3-70b-instruct-fp8-fast
      api_base: https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/v1
      api_key: os.environ/CLOUDFLARE_API_KEY
    model_info:
      id: cf-base
  # ... repeat for FLOSSWARE, HOTMAIL keys

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
  master_key: sk-litellm-flossware-local
  database_url: null
```

### Create env file for systemd

```bash
grep "^export " /home/flossware/.bashrc | grep "=" | sed "s/^export //" | sed "s/['\"]//g" | grep -v "^PATH=" > /home/flossware/.bashrc.env
chown flossware:flossware /home/flossware/.bashrc.env
chmod 600 /home/flossware/.bashrc.env
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
User=flossware
Group=flossware
WorkingDirectory=/home/flossware
EnvironmentFile=/home/flossware/.bashrc.env
ExecStart=/home/flossware/litellm-venv/bin/litellm --config /home/flossware/litellm-config.yaml --host 0.0.0.0 --port 4000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable litellm
systemctl start litellm
# Takes ~50s to start (heavy Python imports)
```

### Verify

```bash
curl http://localhost:4000/v1/models -H "Authorization: Bearer sk-litellm-flossware-local"
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-litellm-flossware-local" \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.5-flash","messages":[{"role":"user","content":"hello"}],"max_tokens":50}'
```

---

## Step 2: SSH Tunnel (for cabin network machines)

Cabin network (192.168.2.x) can't reach aio-01 (192.168.1.x) directly. Create an SSH tunnel on cabin-laptop-02.

```ini
# /etc/systemd/system/litellm-tunnel.service
[Unit]
Description=SSH tunnel to LiteLLM on aio-01:4000
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=sfloess
ExecStart=/usr/bin/autossh -M 0 -N -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -o "ExitOnForwardFailure=yes" -L 0.0.0.0:4000:localhost:4000 aio-01
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable litellm-tunnel
sudo systemctl start litellm-tunnel
```

Now:
- cabin-laptop-02 reaches LiteLLM at `localhost:4000`
- cabin-j7-01 (and other cabin LAN devices) reach it at `192.168.2.5:4000`

---

## Step 3: Install Crush

### From Charm's RPM repo (Fedora/RHEL)

```bash
# Already done on cabin-laptop-02 and aio-01
sudo dnf install crush
```

### From GitHub releases (Termux/ARM64)

```bash
curl -sL "https://github.com/charmbracelet/crush/releases/download/v0.89.0/crush_0.89.0_Linux_arm64.tar.gz" -o crush.tar.gz
tar xzf crush.tar.gz
mv crush /usr/local/bin/  # or $PREFIX/bin on Termux
```

---

## Step 4: Configure Crush

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
      "api_key": "sk-litellm-flossware-local",
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
- `localhost` — if on aio-01 or cabin-laptop-02 (has tunnel)
- `192.168.2.5` — if on cabin-j7-01 or other cabin LAN device
- `aio-01` — if on the home LAN (192.168.1.x)

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

**Fix:** Overwrite the state file (see Step 4 above).

### Crush says "model not available" or "Vertex_ai_betaException"

Google deprecated `gemini-2.5-flash` on newer accounts. Use `gemini-3.5-flash` instead. Check which models work:

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

Normal — heavy Python imports. The systemd service handles this.

### Cerebras rate limits (429)

Cerebras has aggressive TPM limits on free tier. Crush's system prompt is ~14K tokens which can exhaust the limit in one request. Use Gemini as default, Cerebras as fallback only.

### SSH tunnel — cabin devices can't connect

Verify:
1. Tunnel is bound to `0.0.0.0:4000` (not just `127.0.0.1`): `ss -tlnp | grep 4000`
2. Correct IP — check `ip addr show | grep "inet "` (cabin-laptop-02 is 192.168.2.5, not .4)
3. No firewall blocking: `sudo iptables -L INPUT -n`

---

## Architecture Summary

```
                         aio-01 (192.168.1.11)
                        ┌─────────────────────┐
                        │  LiteLLM :4000      │
                        │  (systemd service)   │
                        │                     │
                        │  Round-robins across │
                        │  30+ free API keys:  │
                        │  3x Google           │
                        │  2x Groq             │
                        │  4x Mistral          │
                        │  4x Cerebras         │
                        │  4x OpenRouter       │
                        │  2x Pollinations     │
                        │  3x Cloudflare       │
                        └────────┬────────────┘
                                 │
                          SSH tunnel (:4000)
                                 │
               cabin-laptop-02 (192.168.2.5)
              ┌──────────────────┴──────────────┐
              │  autossh tunnel :4000            │
              │  (systemd: litellm-tunnel)       │
              │                                  │
              │  Crush → localhost:4000           │
              └──────────────┬───────────────────┘
                             │ LAN
              cabin-j7-01 (192.168.2.10)
              ┌──────────────┴───────────────────┐
              │  Crush → 192.168.2.5:4000        │
              └──────────────────────────────────┘
```

---

## Adding a New Machine

1. Install crush (RPM or GitHub release)
2. Copy `~/.config/crush/crush.json` — change `LITELLM_HOST` to the appropriate address
3. Write the state file at `~/.local/share/crush/crush.json`
4. Sync env vars from flossware's bashrc (83+ exports, personal keys only)
5. Test: `crush run "hello"`
6. Verify: `grep ModelProvider ~/.crush/logs/crush.log`

## Adding a New API Key

1. Add the env var to `/home/flossware/.bashrc` on aio-01
2. Regenerate: `grep "^export " .bashrc | grep "=" | sed "s/^export //" | sed "s/['\"]//g" | grep -v "^PATH=" > .bashrc.env`
3. Add a new entry in `/home/flossware/litellm-config.yaml` with the same `model_name` and a unique `model_info.id`
4. Restart: `sudo systemctl restart litellm`
5. Sync env vars to other machines

## Adding a New Provider

1. Add entries to `litellm-config.yaml` using litellm's provider prefix (e.g., `groq/`, `mistral/`, `gemini/`, `openrouter/`)
2. Add fallback rules in `litellm_settings.fallbacks`
3. Add the model to crush's config `models` array in the `litellm` provider
4. Restart litellm, update crush state files on all machines
