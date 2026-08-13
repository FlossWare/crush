# Free AI Model Providers

All providers listed here offer free tiers suitable for LLM inference, embeddings, or both. Multiple accounts per provider multiply your effective rate limits when used with [LiteLLM round-robin](litellm-setup.md).

---

## LLM Inference Providers

### Google AI Studio (Gemini)

- **Signup:** https://aistudio.google.com/
- **Models:** `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3.5-flash`
- **LiteLLM prefix:** `gemini/`
- **Notes:** Some older model names may be deprecated on newer accounts. Check available models: `curl "https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY"`

### Groq

- **Signup:** https://console.groq.com/
- **Models:** `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `gemma2-9b-it`, `mixtral-8x7b-32768`
- **LiteLLM prefix:** `groq/`
- **Notes:** Extremely fast inference. Free tier has TPM limits — large system prompts can exhaust the limit in one request.

### Mistral

- **Signup:** https://console.mistral.ai/
- **Models:** `mistral-small-latest`, `codestral-latest`, `mistral-large-latest`
- **LiteLLM prefix:** `mistral/`
- **Notes:** Codestral is specifically tuned for code generation and review.

### Cerebras

- **Signup:** https://cloud.cerebras.ai/
- **Models:** `llama-3.3-70b`, `llama-3.1-8b`
- **LiteLLM prefix:** `cerebras/`
- **Notes:** Very fast inference on custom hardware. Free tier TPM limits are aggressive — not ideal as a default model for agents with large system prompts.

### OpenRouter

- **Signup:** https://openrouter.ai/
- **Models (free):** `nvidia/nemotron-3-ultra-550b-a55b:free`, `google/gemma-4-31b-it:free`, `meta-llama/llama-3.3-70b-instruct:free`, `qwen/qwen-2.5-72b-instruct:free`, `deepseek/deepseek-chat:free`
- **LiteLLM prefix:** `openrouter/`
- **Notes:** Aggregator with 200+ models. Free models use shared upstream rate limits. Append `:free` to model names for zero-cost routing.

### DeepSeek

- **Signup:** https://platform.deepseek.com/
- **Models:** `deepseek-chat`, `deepseek-coder`
- **LiteLLM prefix:** `deepseek/`
- **Notes:** Strong at code generation and analytical tasks. Also available free via OpenRouter.

### DeepInfra

- **Signup:** https://deepinfra.com/
- **Models:** Various open-source models (Llama, Mistral, Qwen, etc.)
- **LiteLLM prefix:** `deepinfra/`
- **Notes:** Free chat inference for select models. Embedding models may require credits.

### Cloudflare Workers AI

- **Signup:** https://dash.cloudflare.com/
- **Models:** `@cf/meta/llama-3.3-70b-instruct-fp8-fast`, `@cf/meta/llama-3.1-8b-instruct`
- **LiteLLM prefix:** Use `openai/` with custom `api_base`
- **Notes:** Daily free limit resets at midnight UTC. Requires account ID in the API URL.

### Pollinations

- **Signup:** https://pollinations.ai/
- **Models:** `openai-fast` and others via their API
- **LiteLLM prefix:** Use `openai/` with custom `api_base` (`https://text.pollinations.ai/openai`)
- **Notes:** Legacy text API being deprecated for authenticated users. Anonymous requests remain free.

### Cohere

- **Signup:** https://dashboard.cohere.com/
- **Models:** `command-r`, `command-r-plus`
- **LiteLLM prefix:** `cohere/`
- **Notes:** Also offers free embedding and reranking models.

### NVIDIA NIM

- **Signup:** https://build.nvidia.com/
- **Models:** Various (Llama, Mistral, Nemotron, etc.)
- **LiteLLM prefix:** `nvidia_nim/`
- **Notes:** Credits are limited but generous for experimentation. Nemotron models are strong for instruction following.

### OpenAI

- **Signup:** https://platform.openai.com/
- **Models:** `gpt-4o-mini`, `gpt-3.5-turbo`
- **LiteLLM prefix:** `openai/` (default, no prefix needed)
- **Notes:** Free credits are minimal and expire. Not recommended as a primary free provider — use via OpenRouter free tier instead.

### Poolside

- **Signup:** https://platform.poolside.ai/
- **Models:** Code-focused models
- **Notes:** Specialized in code generation.

### EdenAI

- **Signup:** https://www.edenai.co/
- **Models:** Aggregator — routes to multiple providers
- **Notes:** Multi-provider aggregator with unified API. Free tier includes limited credits.

### ZeroLimitAI

- **Signup:** https://zerolimit.ai/
- **Models:** Various open-source models

### ThinkMachines

- **Signup:** https://thinkmachines.ai/
- **Models:** Various

---

## Embedding & Utility Providers

### Jina AI

- **Signup:** https://jina.ai/
- **Models:** `jina-embeddings-v3`, `jina-reranker-v2`
- **Notes:** Embedding and reranking. Also offers free web reader API (`r.jina.ai`) and search API (`s.jina.ai`).

### Voyage AI

- **Signup:** https://www.voyageai.com/
- **Models:** `voyage-3`, `voyage-code-3`, `voyage-3-lite`
- **Notes:** High-quality embeddings, especially for code search.

### HuggingFace

- **Signup:** https://huggingface.co/
- **Models:** Thousands (Llama, Mistral, BERT, sentence-transformers, etc.)
- **Notes:** Free inference is rate-limited and may queue. Good for embeddings (`bge-base-en-v1.5`, `all-MiniLM-L6-v2`).

### Unstructured

- **Signup:** https://unstructured.io/
- **Notes:** Document parsing and chunking, not LLM inference. Useful for ingesting PDFs, DOCX, etc. into LLM pipelines.

---

## Maximizing Free Tier Limits

### Multiple Accounts

Most providers allow multiple accounts. Each account gets its own rate limits. Use [LiteLLM](litellm-setup.md) to round-robin across accounts:

```yaml
# In litellm-config.yaml — same model_name, different keys
- model_name: gemini-3.5-flash
  litellm_params:
    model: gemini/gemini-3.5-flash
    api_key: os.environ/GOOGLE_API_KEY_1
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
