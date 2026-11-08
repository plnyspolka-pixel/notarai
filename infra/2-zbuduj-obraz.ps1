# notarai - etap 2: budowa obrazu kontenera w CodeBuild
#
# Uruchom z katalogu notarai:
#   powershell -ExecutionPolicy Bypass -File infra\2-zbuduj-obraz.ps1
#
# Pakuje WYLACZNIE zacommitowany kod (git archive HEAD) - katalog dane/ i
# niezacommitowane zmiany nigdy nie trafiaja do obrazu. Tag obrazu to skrot
# commita, wiec obraz w ECR zawsze odpowiada konkretnemu stanowi repozytorium.
param(
    [string]$Profil = "",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971"
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot

function Uruchom-Aws {
    # Nie wymuszamy --profile: istniejąca sesja AWS CLI może być z env/SSO.
    $opcje = @("--region", $Region)
    if ($Profil) { $opcje += @("--profile", $Profil) }
    $wynik = & aws @args @opcje
    if ($LASTEXITCODE -ne 0) { throw "Polecenie aws $($args[0]) $($args[1]) nie powiodlo sie (kod $LASTEXITCODE)." }
    return $wynik
}

# Sprawdzenie, ktorego odpowiedz "nie ma" jest oczekiwana. Windows PowerShell 5.1
# przy ErrorActionPreference=Stop zamienia przekierowany stderr programu w blad
# krytyczny, wiec wewnatrz funkcji wracamy do Continue.
function Czy-Aws {
    $ErrorActionPreference = "Continue"
    $opcje = @("--region", $Region)
    if ($Profil) { $opcje += @("--profile", $Profil) }
    & aws @args @opcje 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

Write-Host "== Sprawdzam konto AWS i repozytorium" -ForegroundColor Cyan
if (-not (Czy-Aws sts get-caller-identity)) {
    throw "AWS CLI nie ma aktywnych uprawnien dla tej sesji. Sprawdz profil AWS_PROFILE lub skonfigurowany dostep CLI; logowanie w przegladarce nie jest sesja CLI."
}
$biezace = Uruchom-Aws sts get-caller-identity --query Account --output text
if ($biezace -ne $Konto) { throw "AWS wskazuje konto $biezace, oczekiwane $Konto. Przerywam." }

# Obraz powstaje z "git archive HEAD", wiec odpowiada commitowi zawsze, takze
# gdy na dysku lezy praca w toku. Kiedys bylo to bledem krytycznym, zeby nikt
# nie myslal, ze wdraza swoje niezapisane zmiany. Przy dwoch osobach pracujacych
# w jednym repozytorium blokowalo to jednak wypuszczenie gotowego commita przez
# to, ze ktos obok wlasnie pisze. Zamiast przerywac - mowimy wprost, czego w
# obrazie nie bedzie.
$brudne = git -C $korzen status --porcelain
$tag = (git -C $korzen rev-parse --short=12 HEAD).Trim()
if ($brudne) {
    Write-Host "Uwaga: ponizsze zmiany NIE wejda do obrazu - powstaje on z commita $tag :" -ForegroundColor Yellow
    ($brudne -split "`n") | Where-Object { $_.Trim() } | ForEach-Object { Write-Host "   $_" -ForegroundColor Yellow }
}
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
