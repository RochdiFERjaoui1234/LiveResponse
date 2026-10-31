# Windows execution script
$ErrorActionPreference = "Stop"

if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .venv\Scripts\Activate.ps1
}

if (Test-Path "config\agent.key") {
    $env:SOAR_AGENT_KEY = (Get-Content "config\agent.key").Trim()
} else {
    $env:SOAR_AGENT_KEY = "super_secret_agent_key_default"
}

Write-Host "⚡ Launching Super SOAR console..." -ForegroundColor Cyan
python -m soar --config config\config.yaml $args
