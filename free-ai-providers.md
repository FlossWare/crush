# Free AI Model Providers

All providers listed here offer free tiers suitable for LLM inference, embeddings, or both. Multiple accounts per provider multiply your effective rate limits when used with [LiteLLM round-robin](litellm-setup.md).

---

## How API Keys Flow

```
Provider signup → API key → env var on LiteLLM server → litellm-config.yaml → LiteLLM proxy
                                                                                     ↑
                                                              Crush connects here (master key only)
```

**Crush does NOT need provider API keys.** It authenticates to LiteLLM with a single master key (set in `litellm-config.yaml` under `general_settings.master_key`).

**LiteLLM needs the provider API keys** as environment variables. The `litellm-config.yaml` references them with `os.environ/VAR_NAME` syntax. The systemd service loads them from an env file (see [LiteLLM Setup](litellm-setup.md)).

To add a new provider:
1. Sign up and get an API key
2. Export it in `~/.bashrc` on the LiteLLM server
3. Regenerate the env file: `grep "^export " ~/.bashrc | grep "=" | sed "s/^export //" | sed "s/['\"]//g" | grep -v "^PATH=" > ~/.litellm.env`
4. Reference it in `litellm-config.yaml` as `api_key: os.environ/VAR_NAME`
5. Restart LiteLLM: `sudo systemctl restart litellm`

---

## LLM Inference Providers

### Google AI Studio (Gemini)

- **Signup:** https://aistudio.google.com/
- **Env var:** `GOOGLE_API_KEY`
- **Models:** `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3.5-flash`
- **LiteLLM prefix:** `gemini/`
- **Notes:** Some older model names may be deprecated on newer accounts. Check available models: `curl "https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY"`

### Groq

- **Signup:** https://console.groq.com/
- **Env var:** `GROQ_API_KEY`
- **Models:** `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `gemma2-9b-it`, `mixtral-8x7b-32768`
- **LiteLLM prefix:** `groq/`
- **Notes:** Extremely fast inference. Free tier has TPM limits — large system prompts can exhaust the limit in one request.

### Mistral

- **Signup:** https://console.mistral.ai/
- **Env var:** `MISTRAL_API_KEY`
- **Models:** `mistral-small-latest`, `codestral-latest`, `mistral-large-latest`
- **LiteLLM prefix:** `mistral/`
- **Notes:** Codestral is specifically tuned for code generation and review.

### Cerebras

- **Signup:** https://cloud.cerebras.ai/
- **Env var:** `CEREBRAS_API_KEY`
- **Models:** `llama-3.3-70b`, `llama-3.1-8b`
- **LiteLLM prefix:** `cerebras/`
- **Notes:** Very fast inference on custom hardware. Free tier TPM limits are aggressive — not ideal as a default model for agents with large system prompts.

### OpenRouter

- **Signup:** https://openrouter.ai/
- **Env var:** `OPENROUTER_API_KEY`
- **Models (free):** `nvidia/nemotron-3-ultra-550b-a55b:free`, `google/gemma-4-31b-it:free`, `meta-llama/llama-3.3-70b-instruct:free`, `qwen/qwen-2.5-72b-instruct:free`, `deepseek/deepseek-chat:free`
- **LiteLLM prefix:** `openrouter/`
- **Notes:** Aggregator with 200+ models. Free models use shared upstream rate limits. Append `:free` to model names for zero-cost routing.

### DeepSeek

- **Signup:** https://platform.deepseek.com/
- **Env var:** `DEEPSEEK_API_KEY`
- **Models:** `deepseek-chat`, `deepseek-coder`
- **LiteLLM prefix:** `deepseek/`
- **Notes:** Strong at code generation and analytical tasks. Also available free via OpenRouter.

### DeepInfra

- **Signup:** https://deepinfra.com/
- **Env var:** `DEEPINFRA_API_KEY`
- **Models:** Various open-source models (Llama, Mistral, Qwen, etc.)
- **LiteLLM prefix:** `deepinfra/`
- **Notes:** Free chat inference for select models. Embedding models may require credits.

### Cloudflare Workers AI

- **Signup:** https://dash.cloudflare.com/
- **Env vars:** `CLOUDFLARE_API_KEY`, `CLOUDFLARE_ACCOUNT_ID`
- **Models:** `@cf/meta/llama-3.3-70b-instruct-fp8-fast`, `@cf/meta/llama-3.1-8b-instruct`
- **LiteLLM prefix:** Use `openai/` with custom `api_base`
- **Notes:** Daily free limit resets at midnight UTC. Requires account ID in the API URL: `https://api.cloudflare.com/client/v4/accounts/YOUR_ACCOUNT_ID/ai/v1`

### Pollinations

- **Signup:** https://pollinations.ai/
- **Env var:** `POLLINATIONS_API_KEY`
- **Models:** `openai-fast` and others via their API
- **LiteLLM prefix:** Use `openai/` with custom `api_base` (`https://text.pollinations.ai/openai`)
- **Notes:** Legacy text API being deprecated for authenticated users. Anonymous requests remain free.

### Cohere

- **Signup:** https://dashboard.cohere.com/
- **Env var:** `COHERE_API_KEY`
- **Models:** `command-r`, `command-r-plus`
- **LiteLLM prefix:** `cohere/`
- **Notes:** Also offers free embedding and reranking models.

### NVIDIA NIM

- **Signup:** https://build.nvidia.com/
- **Env var:** `NVIDIA_API_KEY`
- **Models:** Various (Llama, Mistral, Nemotron, etc.)
- **LiteLLM prefix:** `nvidia_nim/`
- **Notes:** Credits are limited but generous for experimentation. Nemotron models are strong for instruction following.

### OpenAI

- **Signup:** https://platform.openai.com/
- **Env var:** `OPENAI_API_KEY`
- **Models:** `gpt-4o-mini`, `gpt-3.5-turbo`
- **LiteLLM prefix:** `openai/` (default, no prefix needed)
- **Notes:** Free credits are minimal and expire. Not recommended as a primary free provider — use via OpenRouter free tier instead.

### Poolside

- **Signup:** https://platform.poolside.ai/
- **Env var:** `POOLSIDE_API_KEY`
- **Models:** Code-focused models
- **Notes:** Specialized in code generation.

### EdenAI

- **Signup:** https://www.edenai.co/
- **Env var:** `EDENAI_API_KEY`
- **Models:** Aggregator — routes to multiple providers
- **Notes:** Multi-provider aggregator with unified API. Free tier includes limited credits.

### ZeroLimitAI

- **Signup:** https://zerolimit.ai/
- **Env var:** `ZEROLIMITAI_API_KEY`
- **Models:** Various open-source models

### ThinkMachines

- **Signup:** https://thinkmachines.ai/
- **Env var:** `THINKMACHINES_API_KEY`
- **Models:** Various

---

## Embedding & Utility Providers

### Jina AI

- **Signup:** https://jina.ai/
- **Env var:** `JINA_API_KEY`
- **Models:** `jina-embeddings-v3`, `jina-reranker-v2`
- **Notes:** Embedding and reranking. Also offers free web reader API (`r.jina.ai`) and search API (`s.jina.ai`).

### Voyage AI

- **Signup:** https://www.voyageai.com/
- **Env var:** `VOYAGEAI_API_KEY`
- **Models:** `voyage-3`, `voyage-code-3`, `voyage-3-lite`
- **Notes:** High-quality embeddings, especially for code search.

### HuggingFace

- **Signup:** https://huggingface.co/
- **Env var:** `HUGGINGFACE_API_KEY`
- **Models:** Thousands (Llama, Mistral, BERT, sentence-transformers, etc.)
- **Notes:** Free inference is rate-limited and may queue. Good for embeddings (`bge-base-en-v1.5`, `all-MiniLM-L6-v2`).

### Unstructured

- **Signup:** https://unstructured.io/
- **Env var:** `UNSTRUCTURED_API_KEY`
- **Notes:** Document parsing and chunking, not LLM inference. Useful for ingesting PDFs, DOCX, etc. into LLM pipelines.

---

## Maximizing Free Tier Limits

### Multiple Accounts

Most providers allow multiple accounts. Each account gets its own rate limits. Use [LiteLLM](litellm-setup.md) to round-robin across accounts automatically.

Use a consistent env var naming pattern for additional accounts:

```
GOOGLE_API_KEY          # primary account
GOOGLE_API_KEY_2        # second account
GOOGLE_API_KEY_3        # third account
```

Then in `litellm-config.yaml`, repeat the same `model_name` block for each key:

```yaml
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
```

### Provider Selection Guide

| Use Case | Recommended Providers | Why |
|---|---|---|
| **Default LLM** | Google Gemini | Generous free limits, fast, large context |
| **Fast inference** | Groq, Cerebras | Hardware-accelerated |
| **Code generation** | Mistral (Codestral), DeepSeek | Purpose-built for code |
| **Diverse consensus** | OpenRouter (free models) | Access many model families through one API |
| **Embeddings** | Jina, Voyage AI, HuggingFace | Generous free tiers |
| **Document parsing** | Unstructured | PDF/DOCX extraction |
| **Fallback / overflow** | Cloudflare, Pollinations | Daily resets, anonymous access |
