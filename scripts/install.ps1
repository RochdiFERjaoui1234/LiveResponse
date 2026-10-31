# PowerShell Installation Script for Windows
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " ⚡ Installing SUPER SOAR on Windows" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "[*] Installing Python dependencies..." -ForegroundColor Yellow
& .venv\Scripts\pip.exe install --upgrade pip
& .venv\Scripts\pip.exe install -r requirements.txt

if (-not (Test-Path "var")) { New-Item -ItemType Directory -Path "var" | Out-Null }
if (-not (Test-Path "config\agent.key")) {
    $bytes = New-Object byte[] 32
    (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($bytes)
    $hex = [BitConverter]::ToString($bytes).Replace("-","").ToLower()
    Set-Content -Path "config\agent.key" -Value $hex
    Write-Host "[*] Generated agent secret key in config\agent.key" -ForegroundColor Green
}

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " [✓] Installation complete! Launch with: .\scripts\run.ps1" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
