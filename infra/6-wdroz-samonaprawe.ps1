# notarai - etap 6: samonaprawa w AWS (stos notarai-samonaprawa)
#
# Uruchom z katalogu notarai, zalogowany jako administrator konta:
#   powershell -ExecutionPolicy Bypass -File infra\6-wdroz-samonaprawe.ps1
#
# Zaklada: tabele DynamoDB, bucket na poprawki, projekt CodeBuild notarai-samonaprawa,
# role (potok i agent zawezony do Bedrock), reguly EventBridge i alarm. Ustawia domyslne
# parametry sterujace /notarai/samonaprawa/tryb (auto) i /notarai/samonaprawa/model.
# Wymaga wczesniej: stosu notarai-budowanie i notarai-aplikacja oraz wdrozonej wersji kodu
# z potokiem (scripts/samonaprawa/potok.py w obrazie z produkcji) - patrz docs/samonaprawa.md.
# Rownowazne polecenie: aws cloudformation deploy --stack-name notarai-samonaprawa
#   --template-file infra/notarai-samonaprawa.yaml --capabilities CAPABILITY_NAMED_IAM --region eu-central-1
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
    throw "AWS CLI nie ma aktywnej sesji. Zaloguj sie (aws login) i uruchom skrypt ponownie."
}
$biezace = Uruchom-Aws sts get-caller-identity --query Account --output text
if ($biezace -ne $Konto) { throw "AWS wskazuje konto $biezace, oczekiwane $Konto. Przerywam." }
foreach ($stos in @("notarai-budowanie", "notarai-aplikacja")) {
    if (-not (Czy-Aws cloudformation describe-stacks --stack-name $stos)) { throw "Brak stosu $stos - wdroz go najpierw (etapy 2 i 3)." }
}

Write-Host "== Walidacja szablonu" -ForegroundColor Cyan
Uruchom-Aws cloudformation validate-template --template-body "file://$korzen/infra/notarai-samonaprawa.yaml" | Out-Null

Write-Host "== Wdrazam stos notarai-samonaprawa" -ForegroundColor Cyan
Uruchom-Aws cloudformation deploy --stack-name notarai-samonaprawa `
    --template-file (Join-Path $korzen "infra/notarai-samonaprawa.yaml") `
    --capabilities CAPABILITY_NAMED_IAM --tags projekt=notarai --no-fail-on-empty-changeset

Write-Host "== Parametry sterujace (tylko gdy ich jeszcze nie ma)" -ForegroundColor Cyan
foreach ($p in @(@("/notarai/samonaprawa/tryb", "auto"), @("/notarai/samonaprawa/model", "eu.anthropic.claude-opus-4-6-v1"))) {
    if (-not (Czy-Aws ssm get-parameter --name $p[0])) {
        Uruchom-Aws ssm put-parameter --name $p[0] --type String --value $p[1] | Out-Null
        Write-Host "   ustawiono $($p[0]) = $($p[1])"
    } else {
        Write-Host "   $($p[0]) juz istnieje - zostawiam"
    }
}

Write-Host "Gotowe. Test bez agenta (nieszkodliwa zmiana w docs/): python scripts/samonaprawa/zglos.py --test" -ForegroundColor Green
Write-Host "Opis i sterowanie: docs/samonaprawa.md" -ForegroundColor Green
