#!/usr/bin/env bash
set -euo pipefail

# Add a new API key to LiteLLM config and restart.
# Run on the LiteLLM server.
#
# Usage:
#   ./add-provider.sh <provider> <env-var-name>
#
# Examples:
#   ./add-provider.sh gemini GOOGLE_API_KEY_3
#   ./add-provider.sh groq GROQ_API_KEY_2
#   ./add-provider.sh mistral MISTRAL_API_KEY_4
#   ./add-provider.sh openrouter OPENROUTER_API_KEY_2
#
# The env var must already be exported in ~/.bashrc.

LITELLM_DIR="${LITELLM_DIR:-$HOME}"
CONFIG_FILE="${LITELLM_DIR}/litellm-config.yaml"
ENV_FILE="${LITELLM_DIR}/.litellm.env"

info()  { echo -e "\033[1;34m==>\033[0m $*"; }
ok()    { echo -e "\033[1;32m  ✓\033[0m $*"; }
warn()  { echo -e "\033[1;33m  !\033[0m $*"; }
err()   { echo -e "\033[1;31m  ✗\033[0m $*" >&2; }

if [ $# -lt 2 ]; then
    echo "Usage: $0 <provider> <env-var-name>"
    echo ""
    echo "Providers: gemini, groq, mistral, cerebras, openrouter, deepseek,"
    echo "           deepinfra, cloudflare, cohere, nvidia, pollinations, openai"
    exit 1
fi

PROVIDER="$1"
ENV_VAR="$2"

# Verify env var exists
if [ -z "${!ENV_VAR:-}" ]; then
    err "Environment variable ${ENV_VAR} is not set."
    err "Export it in ~/.bashrc first: export ${ENV_VAR}='your-api-key'"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    err "Config not found at ${CONFIG_FILE}"
    err "Run setup-litellm.sh first."
    exit 1
fi

# Map provider to model config
case "$PROVIDER" in
    gemini)
        MODEL_NAME="gemini-3.5-flash"
        LITELLM_MODEL="gemini/gemini-3.5-flash"
        ID_PREFIX="gemini-flash"
        ;;
    groq)
        MODEL_NAME="llama-3.3-70b"
        LITELLM_MODEL="groq/llama-3.3-70b-versatile"
        ID_PREFIX="groq-llama"
        ;;
    mistral)
        MODEL_NAME="mistral-small"
        LITELLM_MODEL="mistral/mistral-small-latest"
        ID_PREFIX="mistral-small"
        ;;
    cerebras)
        MODEL_NAME="cerebras-llama"
        LITELLM_MODEL="cerebras/llama-3.3-70b"
        ID_PREFIX="cerebras"
        ;;
    openrouter)
        MODEL_NAME="nemotron-ultra"
        LITELLM_MODEL="openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
        ID_PREFIX="or-nemotron"
        ;;
    deepseek)
        MODEL_NAME="deepseek-chat"
        LITELLM_MODEL="deepseek/deepseek-chat"
        ID_PREFIX="deepseek"
        ;;
    deepinfra)
        MODEL_NAME="deepinfra-llama"
        LITELLM_MODEL="deepinfra/meta-llama/Llama-3.3-70B-Instruct"
        ID_PREFIX="deepinfra"
        ;;
    cohere)
        MODEL_NAME="command-r"
        LITELLM_MODEL="cohere/command-r"
        ID_PREFIX="cohere"
        ;;
    nvidia)
        MODEL_NAME="nvidia-llama"
        LITELLM_MODEL="nvidia_nim/meta/llama-3.3-70b-instruct"
        ID_PREFIX="nvidia"
        ;;
    openai)
        MODEL_NAME="gpt-4o-mini"
        LITELLM_MODEL="gpt-4o-mini"
        ID_PREFIX="openai"
        ;;
    *)
        err "Unknown provider: ${PROVIDER}"
        echo "Supported: gemini, groq, mistral, cerebras, openrouter, deepseek, deepinfra, cohere, nvidia, openai"
        exit 1
        ;;
esac

# Generate unique ID
EXISTING=$(grep -c "id: ${ID_PREFIX}" "$CONFIG_FILE" 2>/dev/null || echo 0)
NEXT_ID=$((EXISTING + 1))
UNIQUE_ID="${ID_PREFIX}-${NEXT_ID}"

info "Adding ${PROVIDER} key (${ENV_VAR}) as ${UNIQUE_ID}..."

# Find the insertion point (before litellm_settings)
# Add the new model entry before the settings section
ENTRY="  - model_name: ${MODEL_NAME}
    litellm_params:
      model: ${LITELLM_MODEL}
      api_key: os.environ/${ENV_VAR}
    model_info:
      id: ${UNIQUE_ID}"

# Insert before litellm_settings line
if grep -q "^litellm_settings:" "$CONFIG_FILE"; then
    sed -i "/^litellm_settings:/i\\
${ENTRY}" "$CONFIG_FILE"
else
    echo "$ENTRY" >> "$CONFIG_FILE"
fi

ok "Added to ${CONFIG_FILE}"

# Regenerate env file
info "Regenerating env file..."
if [ -f "$HOME/.bashrc" ]; then
    grep "^export " "$HOME/.bashrc" \
        | grep "=" \
        | sed "s/^export //" \
        | sed "s/['\"]//g" \
        | grep -v "^PATH=" \
        > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    ok "Updated ${ENV_FILE}"
fi

# Restart LiteLLM
info "Restarting LiteLLM..."
if systemctl is-active litellm &>/dev/null; then
    sudo systemctl restart litellm
    ok "LiteLLM restarted"
    echo ""
    echo "  Verify: curl http://localhost:4000/v1/models -H 'Authorization: Bearer sk-litellm-local' | python3 -m json.tool"
else
    warn "LiteLLM service not running. Start it with: sudo systemctl start litellm"
fi
