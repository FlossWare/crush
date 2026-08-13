#!/usr/bin/env bash
set -euo pipefail

# Setup Crush (Charm's terminal coding agent) to use LiteLLM proxy.
# Works on Linux (x86_64, arm64), macOS (arm64, x86_64), and Termux (Android).
# For Windows, see setup-crush.ps1.

LITELLM_HOST="${LITELLM_HOST:-localhost}"
LITELLM_PORT="${LITELLM_PORT:-4000}"
LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-litellm-local}"
DEFAULT_MODEL="${DEFAULT_MODEL:-gemini-3.5-flash}"
SMALL_MODEL="${SMALL_MODEL:-mistral-small}"

info()  { echo -e "\033[1;34m==>\033[0m $*"; }
ok()    { echo -e "\033[1;32m  ✓\033[0m $*"; }
warn()  { echo -e "\033[1;33m  !\033[0m $*"; }
err()   { echo -e "\033[1;31m  ✗\033[0m $*" >&2; }

# ── Detect platform ──────────────────────────────────────────────────

detect_platform() {
    OS="$(uname -s)"
    ARCH="$(uname -m)"
    IS_TERMUX=false

    if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux" ] || [[ "${PREFIX:-}" == *com.termux* ]]; then
        IS_TERMUX=true
        OS="Linux"
        ARCH="arm64"
    fi

    case "$OS" in
        Linux)  OS_NAME="Linux" ;;
        Darwin) OS_NAME="Darwin" ;;
        *)      err "Unsupported OS: $OS"; exit 1 ;;
    esac

    case "$ARCH" in
        x86_64|amd64)   ARCH_NAME="x86_64" ;;
        aarch64|arm64)  ARCH_NAME="arm64" ;;
        *)              err "Unsupported architecture: $ARCH"; exit 1 ;;
    esac

    ok "Platform: ${OS_NAME} ${ARCH_NAME}$(${IS_TERMUX} && echo ' (Termux)' || true)"
}

# ── Install Crush ─────────────────────────────────────────────────────

install_crush() {
    if command -v crush &>/dev/null; then
        CURRENT_VER=$(crush --version 2>/dev/null | head -1 || echo "unknown")
        ok "Crush already installed: ${CURRENT_VER}"
        read -rp "    Reinstall? [y/N] " ans
        if [[ ! "$ans" =~ ^[Yy] ]]; then
            return
        fi
    fi

    info "Installing Crush..."

    # Try package manager first (Fedora/RHEL)
    if command -v dnf &>/dev/null && ! $IS_TERMUX; then
        if sudo dnf install -y crush 2>/dev/null; then
            ok "Installed via dnf"
            return
        fi
        warn "Not in dnf repos, falling back to GitHub release"
    fi

    # Check for downloader
    if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
        err "Neither curl nor wget found. Install one first."
        exit 1
    fi

    # GitHub release
    TARBALL="crush_${OS_NAME}_${ARCH_NAME}.tar.gz"
    DOWNLOAD_URL="https://github.com/charmbracelet/crush/releases/latest/download/${TARBALL}"

    info "Downloading ${DOWNLOAD_URL}..."

    TMPDIR=$(mktemp -d "${HOME}/.crush-install.XXXXXX")
    trap "rm -rf ${TMPDIR}" EXIT

    if command -v curl &>/dev/null; then
        curl -sfL "$DOWNLOAD_URL" -o "${TMPDIR}/${TARBALL}"
    elif command -v wget &>/dev/null; then
        wget -q "$DOWNLOAD_URL" -O "${TMPDIR}/${TARBALL}"
    else
        err "Neither curl nor wget found."
        exit 1
    fi

    tar xzf "${TMPDIR}/${TARBALL}" -C "$TMPDIR"

    if $IS_TERMUX; then
        INSTALL_DIR="${PREFIX}/bin"
    elif [ -w /usr/local/bin ]; then
        INSTALL_DIR="/usr/local/bin"
    else
        INSTALL_DIR="$HOME/.local/bin"
        mkdir -p "$INSTALL_DIR"
        if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
            warn "Add ${INSTALL_DIR} to your PATH"
        fi
    fi

    if [ -w "$INSTALL_DIR" ]; then
        mv "${TMPDIR}/crush" "${INSTALL_DIR}/crush"
    else
        sudo mv "${TMPDIR}/crush" "${INSTALL_DIR}/crush"
    fi

    chmod +x "${INSTALL_DIR}/crush"
    ok "Installed to ${INSTALL_DIR}/crush"
}

# ── Query available models from LiteLLM ──────────────────────────────

query_models() {
    info "Querying LiteLLM for available models..."

    LITELLM_URL="http://${LITELLM_HOST}:${LITELLM_PORT}"

    if ! curl -sf "${LITELLM_URL}/health" &>/dev/null; then
        warn "LiteLLM not reachable at ${LITELLM_URL}"
        warn "Set LITELLM_HOST and LITELLM_PORT, or run setup-litellm.sh first."
        warn "Proceeding with default model list."
        AVAILABLE_MODELS=""
        return
    fi

    AVAILABLE_MODELS=$(curl -sf "${LITELLM_URL}/v1/models" \
        -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
        | python3 -c "
import json, sys
data = json.load(sys.stdin)
for m in data.get('data', []):
    print(m['id'])
" 2>/dev/null | sort -u)

    if [ -n "$AVAILABLE_MODELS" ]; then
        MODEL_COUNT=$(echo "$AVAILABLE_MODELS" | wc -l)
        ok "Found $MODEL_COUNT models on LiteLLM"
    else
        warn "Could not list models. Using defaults."
    fi
}

# ── Generate Crush config ─────────────────────────────────────────────

generate_config() {
    info "Generating Crush config..."

    if $IS_TERMUX; then
        CONFIG_DIR="${HOME}/.config/crush"
        STATE_DIR="${HOME}/.local/share/crush"
    else
        CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/crush"
        STATE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/crush"
    fi

    mkdir -p "$CONFIG_DIR" "$STATE_DIR"

    CONFIG_FILE="${CONFIG_DIR}/crush.json"
    STATE_FILE="${STATE_DIR}/crush.json"

    # Build models array from available or defaults
    MODELS_JSON="["
    FIRST=true

    add_model_entry() {
        local id="$1"
        local name="$2"
        if ! $FIRST; then MODELS_JSON+=","; fi
        MODELS_JSON+=$'\n'"        { \"id\": \"${id}\", \"name\": \"${name}\" }"
        FIRST=false
    }

    if [ -n "${AVAILABLE_MODELS:-}" ]; then
        while IFS= read -r model; do
            case "$model" in
                gemini-3.5-flash)   add_model_entry "$model" "Gemini 3.5 Flash" ;;
                gemini-3.5-pro)     add_model_entry "$model" "Gemini 3.5 Pro" ;;
                llama-3.3-70b)      add_model_entry "$model" "Llama 3.3 70B (Groq)" ;;
                mistral-small)      add_model_entry "$model" "Mistral Small" ;;
                codestral)          add_model_entry "$model" "Codestral" ;;
                cerebras-llama)     add_model_entry "$model" "Cerebras Llama" ;;
                nemotron-ultra)     add_model_entry "$model" "Nemotron Ultra (OpenRouter)" ;;
                gemma-4-31b)        add_model_entry "$model" "Gemma 4 31B (OpenRouter)" ;;
                deepseek-chat)      add_model_entry "$model" "DeepSeek Chat" ;;
                command-r)          add_model_entry "$model" "Cohere Command R" ;;
                *)                  add_model_entry "$model" "$model" ;;
            esac
        done <<< "$AVAILABLE_MODELS"
    else
        add_model_entry "gemini-3.5-flash" "Gemini 3.5 Flash"
        add_model_entry "llama-3.3-70b" "Llama 3.3 70B (Groq)"
        add_model_entry "mistral-small" "Mistral Small"
        add_model_entry "codestral" "Codestral"
        add_model_entry "cerebras-llama" "Cerebras Llama"
    fi

    MODELS_JSON+=$'\n'"      ]"

    LITELLM_URL="http://${LITELLM_HOST}:${LITELLM_PORT}/v1"

    if [ -f "$CONFIG_FILE" ]; then
        cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"
        warn "Backed up existing config to ${CONFIG_FILE}.bak"
    fi

    cat > "$CONFIG_FILE" << EOF
{
  "\$schema": "https://charm.land/crush.json",
  "providers": {
    "litellm": {
      "type": "openai-compat",
      "base_url": "${LITELLM_URL}",
      "api_key": "${LITELLM_MASTER_KEY}",
      "flat_rate": true,
      "discover_models": false,
      "models": ${MODELS_JSON}
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
      "model": "${DEFAULT_MODEL}",
      "provider": "litellm"
    },
    "large": {
      "model": "${DEFAULT_MODEL}",
      "provider": "litellm"
    },
    "small": {
      "model": "${SMALL_MODEL}",
      "provider": "litellm"
    }
  }
}
EOF

    ok "Config: ${CONFIG_FILE}"

    # Write state file to match
    cat > "$STATE_FILE" << EOF
{"models":{"default":{"model":"${DEFAULT_MODEL}","provider":"litellm","max_tokens":1048576},"small":{"model":"${SMALL_MODEL}","provider":"litellm","max_tokens":32768},"large":{"model":"${DEFAULT_MODEL}","provider":"litellm","max_tokens":1048576}},"recent_models":{"default":[{"model":"${DEFAULT_MODEL}","provider":"litellm"}],"small":[{"model":"${SMALL_MODEL}","provider":"litellm"}],"large":[{"model":"${DEFAULT_MODEL}","provider":"litellm"}]}}
EOF

    ok "State:  ${STATE_FILE}"
}

# ── Verify ────────────────────────────────────────────────────────────

verify() {
    info "Verifying Crush installation..."

    if ! command -v crush &>/dev/null; then
        err "Crush not found in PATH"
        exit 1
    fi

    CRUSH_VER=$(crush --version 2>/dev/null | head -1 || echo "unknown")
    ok "Crush version: ${CRUSH_VER}"

    echo ""
    info "Setup complete!"
    echo "  Config: ${CONFIG_FILE}"
    echo "  State:  ${STATE_FILE}"
    echo "  LiteLLM: http://${LITELLM_HOST}:${LITELLM_PORT}"
    echo ""
    echo "  Test:  crush run 'Say hello'"
    echo ""

    if [ "${LITELLM_HOST}" = "localhost" ]; then
        echo "  If LiteLLM runs on a different machine, re-run with:"
        echo "    LITELLM_HOST=<ip-or-hostname> ./setup-crush.sh"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────

detect_platform
install_crush
query_models
generate_config
verify
