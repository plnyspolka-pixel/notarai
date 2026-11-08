# notarai - etap 4 (jednorazowo): wdrazanie z GitHub bez logowania do AWS
#
# Uruchom z katalogu notarai, zalogowany jako administrator konta:
#   powershell -ExecutionPolicy Bypass -File infra\4-polacz-github.ps1
#
# Zaklada stos notarai-github: dostawce OIDC GitHuba i dwie role
# (notarai-github-wdrozenie, notarai-cloudformation). Zadnych kluczy dostepu -
# GitHub dostaje poswiadczenia waznie godzine, tylko dla galezi master.
# Od tej chwili kazdy push na master, po zielonych testach, sam buduje obraz
# i podmienia aplikacje (.github/workflows/wdrozenie.yml).
param(
    [string]$Profil = "",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971"
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot

function Uruchom-Aws {
    $opcje = @("--region", $Region)
    if ($Profil) { $opcje += @("--profile", $Profil) }
    $wynik = & aws @args @opcje
    if ($LASTEXITCODE -ne 0) { throw "Polecenie aws $($args[0]) $($args[1]) nie powiodlo sie (kod $LASTEXITCODE)." }
    return $wynik
}
function Czy-Aws {
    $ErrorActionPreference = "Continue"
    $opcje = @("--region", $Region)
    if ($Profil) { $opcje += @("--profile", $Profil) }
    & aws @args @opcje 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

Write-Host "== Sprawdzam konto AWS" -ForegroundColor Cyan
if (-not (Czy-Aws sts get-caller-identity)) {
    throw "AWS CLI nie ma aktywnej sesji. Zaloguj sie: aws login --profile notarai-admin, potem uruchom skrypt z -Profil notarai-admin."
}
$biezace = Uruchom-Aws sts get-caller-identity --query Account --output text
if ($biezace -ne $Konto) { throw "AWS wskazuje konto $biezace, oczekiwane $Konto. Przerywam." }

# Dostawca OIDC GitHuba moze byc w koncie tylko jeden - nie zakladamy drugiego.
$dostawcy = Uruchom-Aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[].Arn" --output text
$nowy = "tak"
if ($dostawcy -match "oidc-provider/token\.actions\.githubusercontent\.com") {
    $nowy = "nie"
    Write-Host "   dostawca OIDC GitHuba juz istnieje - uzyje istniejacego"
}

Write-Host "== Stos notarai-github" -ForegroundColor Cyan
Uruchom-Aws cloudformation deploy --stack-name notarai-github `
    --template-file "$korzen\infra\notarai-github.yaml" `
    --capabilities CAPABILITY_NAMED_IAM --tags projekt=notarai `
    --no-fail-on-empty-changeset `
    --parameter-overrides "UtworzDostawceOidc=$nowy" | Out-Host

Write-Host ""
Write-Host "== Gotowe" -ForegroundColor Green
Write-Host "   Od teraz: commit + push na master (albo merge pull requesta)."
Write-Host "   GitHub sam uruchomi testy, zbuduje obraz i podmieni aplikacje."
Write-Host "   Postep: https://github.com/plnyspolka-pixel/notarai/actions"
Write-Host "   Reczne wdrozenie: Actions -> 'NotarAI - wdrozenie na app.notarai.pl' -> Run workflow."
