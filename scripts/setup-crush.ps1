# Setup Crush (Charm's terminal coding agent) to use LiteLLM proxy.
# Run in PowerShell on Windows.
#
# Usage:
#   .\setup-crush.ps1
#   .\setup-crush.ps1 -LiteLLMHost 192.168.1.100 -LiteLLMPort 4000

param(
    [string]$LiteLLMHost = "localhost",
    [int]$LiteLLMPort = 4000,
    [string]$LiteLLMMasterKey = "sk-litellm-local",
    [string]$DefaultModel = "gemini-3.5-flash",
    [string]$SmallModel = "mistral-small"
)

$ErrorActionPreference = "Stop"

function Write-Info  { Write-Host "==> $args" -ForegroundColor Cyan }
function Write-Ok    { Write-Host "  ✓ $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "  ! $args" -ForegroundColor Yellow }
function Write-Err   { Write-Host "  ✗ $args" -ForegroundColor Red }

# ── Install Crush ─────────────────────────────────────────────────────

Write-Info "Checking for Crush..."

$crushPath = Get-Command crush -ErrorAction SilentlyContinue
if ($crushPath) {
    $ver = & crush --version 2>$null | Select-Object -First 1
    Write-Ok "Crush already installed: $ver"
} else {
    Write-Info "Installing Crush..."

    # Detect architecture
    $arch = if ([Environment]::Is64BitOperatingSystem) { "x86_64" } else { "i386" }
    $tarball = "crush_Windows_${arch}.zip"
    $url = "https://github.com/charmbracelet/crush/releases/latest/download/$tarball"

    $tmpDir = Join-Path $env:TEMP "crush-install-$(Get-Random)"
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

    Write-Info "Downloading $url..."
    Invoke-WebRequest -Uri $url -OutFile (Join-Path $tmpDir $tarball) -UseBasicParsing

    Expand-Archive -Path (Join-Path $tmpDir $tarball) -DestinationPath $tmpDir -Force

    $installDir = Join-Path $env:LOCALAPPDATA "Programs\crush"
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    Copy-Item (Join-Path $tmpDir "crush.exe") -Destination (Join-Path $installDir "crush.exe") -Force

    # Add to PATH if not already there
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -notlike "*$installDir*") {
        [Environment]::SetEnvironmentVariable("PATH", "$userPath;$installDir", "User")
        $env:PATH = "$env:PATH;$installDir"
        Write-Warn "Added $installDir to PATH (restart terminal to take effect)"
    }

    Remove-Item -Recurse -Force $tmpDir
    Write-Ok "Installed to $installDir\crush.exe"
}

# ── Query LiteLLM for available models ────────────────────────────────

Write-Info "Querying LiteLLM at ${LiteLLMHost}:${LiteLLMPort}..."

$litellmUrl = "http://${LiteLLMHost}:${LiteLLMPort}"
$availableModels = @()

try {
    $health = Invoke-RestMethod -Uri "$litellmUrl/health" -TimeoutSec 5
    $modelsResp = Invoke-RestMethod -Uri "$litellmUrl/v1/models" `
        -Headers @{ "Authorization" = "Bearer $LiteLLMMasterKey" } `
        -TimeoutSec 10
    $availableModels = $modelsResp.data | ForEach-Object { $_.id } | Sort-Object -Unique
    Write-Ok "Found $($availableModels.Count) models"
} catch {
    Write-Warn "LiteLLM not reachable. Using default model list."
    Write-Warn "Set -LiteLLMHost and -LiteLLMPort if LiteLLM runs elsewhere."
}

# ── Generate model list ───────────────────────────────────────────────

$modelNames = @{
    "gemini-3.5-flash"  = "Gemini 3.5 Flash"
    "gemini-3.5-pro"    = "Gemini 3.5 Pro"
    "llama-3.3-70b"     = "Llama 3.3 70B (Groq)"
    "mistral-small"     = "Mistral Small"
    "codestral"         = "Codestral"
    "cerebras-llama"    = "Cerebras Llama"
    "nemotron-ultra"    = "Nemotron Ultra (OpenRouter)"
    "gemma-4-31b"       = "Gemma 4 31B (OpenRouter)"
    "deepseek-chat"     = "DeepSeek Chat"
    "command-r"         = "Cohere Command R"
}

if ($availableModels.Count -gt 0) {
    $modelEntries = $availableModels | ForEach-Object {
        $name = if ($modelNames.ContainsKey($_)) { $modelNames[$_] } else { $_ }
        @{ id = $_; name = $name }
    }
} else {
    $modelEntries = @(
        @{ id = "gemini-3.5-flash"; name = "Gemini 3.5 Flash" },
        @{ id = "llama-3.3-70b"; name = "Llama 3.3 70B (Groq)" },
        @{ id = "mistral-small"; name = "Mistral Small" },
        @{ id = "codestral"; name = "Codestral" },
        @{ id = "cerebras-llama"; name = "Cerebras Llama" }
    )
}

# ── Write config ──────────────────────────────────────────────────────

Write-Info "Writing Crush config..."

$configDir = Join-Path $env:APPDATA "crush"
$stateDir = Join-Path $env:LOCALAPPDATA "crush"
New-Item -ItemType Directory -Path $configDir -Force | Out-Null
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

$configFile = Join-Path $configDir "crush.json"
$stateFile = Join-Path $stateDir "crush.json"

# Backup existing
if (Test-Path $configFile) {
    Copy-Item $configFile "${configFile}.bak"
    Write-Warn "Backed up existing config"
}

$config = @{
    "`$schema" = "https://charm.land/crush.json"
    providers = @{
        litellm = @{
            type = "openai-compat"
            base_url = "http://${LiteLLMHost}:${LiteLLMPort}/v1"
            api_key = $LiteLLMMasterKey
            flat_rate = $true
            discover_models = $false
            models = $modelEntries
        }
        anthropic = @{ disable = $true }
        openai = @{ disable = $true }
        deepseek = @{ disable = $true }
        cohere = @{ disable = $true }
        xai = @{ disable = $true }
        azure = @{ disable = $true }
        bedrock = @{ disable = $true }
        "bedrock-europe" = @{ disable = $true }
        copilot = @{ disable = $true }
        vercel = @{ disable = $true }
        vertexai = @{ disable = $true }
    }
    models = @{
        default = @{ model = $DefaultModel; provider = "litellm" }
        large   = @{ model = $DefaultModel; provider = "litellm" }
        small   = @{ model = $SmallModel;   provider = "litellm" }
    }
}

$config | ConvertTo-Json -Depth 10 | Set-Content $configFile -Encoding UTF8
Write-Ok "Config: $configFile"

# State file
$state = @{
    models = @{
        default = @{ model = $DefaultModel; provider = "litellm"; max_tokens = 1048576 }
        small   = @{ model = $SmallModel;   provider = "litellm"; max_tokens = 32768 }
        large   = @{ model = $DefaultModel; provider = "litellm"; max_tokens = 1048576 }
    }
    recent_models = @{
        default = @(@{ model = $DefaultModel; provider = "litellm" })
        small   = @(@{ model = $SmallModel;   provider = "litellm" })
        large   = @(@{ model = $DefaultModel; provider = "litellm" })
    }
}

$state | ConvertTo-Json -Depth 10 -Compress | Set-Content $stateFile -Encoding UTF8
Write-Ok "State:  $stateFile"

# ── Done ──────────────────────────────────────────────────────────────

Write-Host ""
Write-Info "Setup complete!"
Write-Host "  Config:  $configFile"
Write-Host "  State:   $stateFile"
Write-Host "  LiteLLM: http://${LiteLLMHost}:${LiteLLMPort}"
Write-Host ""
Write-Host "  Test: crush run 'Say hello'"
Write-Host ""

if ($LiteLLMHost -eq "localhost") {
    Write-Host "  If LiteLLM runs on a different machine, re-run with:"
    Write-Host "    .\setup-crush.ps1 -LiteLLMHost <ip-or-hostname>"
}
