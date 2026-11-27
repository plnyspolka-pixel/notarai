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
$plainKey = Test-Path (Join-Path $env:NOTARAI_V2_HOME "vault.key")
$plainToken = Test-Path (Join-Path $env:NOTARAI_V2_HOME "api.token")
$protectedKey = Test-Path (Join-Path $env:NOTARAI_V2_HOME "vault.key.dpapi")
$protectedToken = Test-Path (Join-Path $env:NOTARAI_V2_HOME "api.token.dpapi")
if (-not ($plainKey -or $plainToken -or $protectedKey -or $protectedToken)) {
    & $python -m worker.init_vault
    if ($LASTEXITCODE -ne 0) { throw "Vault initialization failed" }
} elseif (($plainKey -ne $plainToken) -or ($protectedKey -ne $protectedToken) -or ($plainKey -and $protectedKey)) {
    throw "Incomplete or ambiguous vault initialization. Do not overwrite existing keys."
}
Write-Host "Development only: http://127.0.0.1:8765/v2/pocket"
Write-Host "Run the pair_cli command in a second PowerShell with the same NOTARAI_V2_HOME."
& $python -m worker.api
