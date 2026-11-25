# notarai - etap 7: magazyn aktywacji rejestrow panstwowych (stos notarai-rejestry)
#   powershell -ExecutionPolicy Bypass -File infra\7-wdroz-rejestry.ps1
# Tworzy: klucz KMS, tabele DynamoDB notarai-rejestry (dane osobowe w postaci skrotow, eu-central-1)
# i polityke roli zadania do sejfu kluczy notariuszy (Secrets Manager notarai/rejestry/*).
# Wymaga wczesniej stosu notarai-aplikacja (rola notarai-ecs-zadanie). Opis: docs/aktywacja-rejestrow-gov03.md
param([string]$Profil = "", [string]$Region = "eu-central-1")
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot
$opcje = @("--region", $Region)
if ($Profil) { $opcje += @("--profile", $Profil) }
& aws cloudformation deploy --stack-name notarai-rejestry `
    --template-file (Join-Path $korzen "infra\notarai-rejestry.yaml") `
    --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset @opcje
if ($LASTEXITCODE -ne 0) { throw "Wdrozenie stosu notarai-rejestry nie powiodlo sie." }
Write-Host "Gotowe: stos notarai-rejestry (tabela notarai-rejestry, alias/notarai-rejestry)."
