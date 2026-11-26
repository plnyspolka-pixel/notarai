# Development only. Never use production documents.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not $env:NOTARAI_V2_HOME) {
    $env:NOTARAI_V2_HOME = Join-Path $env:LOCALAPPDATA "NotarAI\V2-dev"
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python environment creation failed" }
}
$python = ".venv\Scripts\python.exe"
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
$key = Join-Path $env:NOTARAI_V2_HOME "vault.key"
$token = Join-Path $env:NOTARAI_V2_HOME "api.token"
if (-not (Test-Path $key) -and -not (Test-Path $token)) {
    & $python -m worker.init_vault
    if ($LASTEXITCODE -ne 0) { throw "Vault initialization failed" }
}
if (-not (Test-Path $key) -or -not (Test-Path $token)) {
    throw "Incomplete vault initialization. Do not overwrite existing keys."
}
Write-Host "Development only: http://127.0.0.1:8765/v2/pocket"
Write-Host "Run the pair_cli command in a second PowerShell with the same NOTARAI_V2_HOME."
& $python -m worker.api
