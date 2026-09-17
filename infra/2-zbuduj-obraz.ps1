# notarai - etap 2: budowa obrazu kontenera w CodeBuild
#
# Uruchom z katalogu notarai:
#   powershell -ExecutionPolicy Bypass -File infra\2-zbuduj-obraz.ps1
#
# Pakuje WYLACZNIE zacommitowany kod (git archive HEAD) - katalog dane/ i
# niezacommitowane zmiany nigdy nie trafiaja do obrazu. Tag obrazu to skrot
# commita, wiec obraz w ECR zawsze odpowiada konkretnemu stanowi repozytorium.
param(
    [string]$Profil = "notarai-admin",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971"
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot

function Uruchom-Aws {
    $wynik = & aws @args --profile $Profil --region $Region
    if ($LASTEXITCODE -ne 0) { throw "Polecenie aws $($args[0]) $($args[1]) nie powiodlo sie (kod $LASTEXITCODE)." }
    return $wynik
}

# Sprawdzenie, ktorego odpowiedz "nie ma" jest oczekiwana. Windows PowerShell 5.1
# przy ErrorActionPreference=Stop zamienia przekierowany stderr programu w blad
# krytyczny, wiec wewnatrz funkcji wracamy do Continue.
function Czy-Aws {
    $ErrorActionPreference = "Continue"
    & aws @args --profile $Profil --region $Region 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

Write-Host "== Sprawdzam konto AWS i repozytorium" -ForegroundColor Cyan
if (-not (Czy-Aws sts get-caller-identity)) {
    throw "Sesja profilu $Profil nie dziala. Odnow ja poleceniem:`n  aws login --profile $Profil --region $Region`nLink z terminala otworz w tym oknie Chrome, w ktorym jestes zalogowana do konsoli AWS."
}
$biezace = Uruchom-Aws sts get-caller-identity --query Account --output text
if ($biezace -ne $Konto) { throw "Profil $Profil wskazuje konto $biezace, oczekiwane $Konto. Przerywam." }

$brudne = git -C $korzen status --porcelain
if ($brudne) { throw "W repozytorium sa niezacommitowane zmiany. Zacommituj je, zeby obraz odpowiadal commitowi." }
$tag = (git -C $korzen rev-parse --short=12 HEAD).Trim()
Write-Host "   konto $biezace, commit $tag"

$wyjscia = Uruchom-Aws cloudformation describe-stacks --stack-name notarai-budowanie --query "Stacks[0].Outputs" --output json | Out-String | ConvertFrom-Json
$bucket  = ($wyjscia | Where-Object OutputKey -eq "BucketZrodel").OutputValue
$projekt = ($wyjscia | Where-Object OutputKey -eq "ProjektBudowania").OutputValue
$repo    = ($wyjscia | Where-Object OutputKey -eq "RepozytoriumUri").OutputValue
$nazwaRepo = $repo.Split("/", 2)[1]

if (Czy-Aws ecr describe-images --repository-name $nazwaRepo --image-ids "imageTag=$tag") {
    Write-Host "== Obraz $($repo):$tag juz jest w ECR - pomijam budowanie" -ForegroundColor Green
    Write-Host "Dalej: powershell -ExecutionPolicy Bypass -File infra\3-wdroz-aplikacje.ps1"
    return
}

Write-Host "== Pakuje kod z commita $tag" -ForegroundColor Cyan
$paczka = Join-Path $env:TEMP "notarai-zrodla-$tag.zip"
git -C $korzen archive --format=zip -o $paczka HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive nie powiodl sie." }
Uruchom-Aws s3 cp $paczka "s3://$bucket/notarai/zrodla.zip" --only-show-errors | Out-Host
Remove-Item $paczka

Write-Host "== Buduje obraz w CodeBuild (zwykle 3-6 minut)" -ForegroundColor Cyan
$idBudowy = Uruchom-Aws codebuild start-build --project-name $projekt `
    --environment-variables-override "name=IMAGE_TAG,value=$tag,type=PLAINTEXT" `
    --query "build.id" --output text

do {
    Start-Sleep -Seconds 20
    $b = Uruchom-Aws codebuild batch-get-builds --ids $idBudowy --query "builds[0].[buildStatus,currentPhase]" --output text
    $stan = $b -split "`t"
    Write-Host ("   {0:HH:mm:ss}  {1}  faza: {2}" -f (Get-Date), $stan[0], $stan[1])
} while ($stan[0] -eq "IN_PROGRESS")

if ($stan[0] -ne "SUCCEEDED") {
    $link = Uruchom-Aws codebuild batch-get-builds --ids $idBudowy --query "builds[0].logs.deepLink" --output text
    throw "Budowanie zakonczone statusem $($stan[0]). Logi: $link"
}

Write-Host ""
Write-Host "== Obraz gotowy: $($repo):$tag" -ForegroundColor Green
Write-Host "Dalej: powershell -ExecutionPolicy Bypass -File infra\3-wdroz-aplikacje.ps1"
