# Build the double-click executable for Live Response.
# Output: <project root>\LiveResponse.exe  — run it and the console opens in your browser.
#
# Prerequisites (one time):
#   pip install pyinstaller
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

python -m PyInstaller `
  --name LiveResponse `
  --onefile `
  --noconsole `
  --add-data "soar\static;soar\static" `
  run.py

if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

Copy-Item "dist\LiveResponse.exe" "LiveResponse.exe" -Force
Write-Host ""
Write-Host "Build complete: $root\LiveResponse.exe"
Write-Host "Run it to start the server and open the web console automatically."
Write-Host "Keep it in the project root so config\ and playbooks\ are found."
