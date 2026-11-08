# NotarAI: jeden proces wydania aplikacji i strony WWW na produkcję.
# Użycie na Windows w lokalnym repo NotarAI:
#   powershell -ExecutionPolicy Bypass -File infra\wydaj-rezerwacje.ps1
#
# Wymaga zalogowanego profilu AWS notarai-admin z uprawnieniami
# do CodeBuild, ECS, CloudFormation, S3 i AWS Secrets Manager oraz profilu FTPS.
# Sekrety pozostają w AWS i są odczytywane wyłącznie w runtime przez asm-exec.
#
# Kolejność: git master -> CodeBuild/ECR -> CloudFormation/ECS ->
# sprawdzenie nowego portalu -> kopia FTP -> strona notarai.pl -> sprawdzenie CTA.
param(
  [string]$Profil = "notarai-admin",
  [string]$Region = "eu-central-1",
  [switch]$BezStrony
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot
Push-Location $korzen
try {
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Brak git. Zainstaluj Git for Windows."
  }
  if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "Brak AWS CLI. Zainstaluj AWS CLI v2."
  }
  $zmiany = git status --porcelain
  if ($LASTEXITCODE -ne 0) { throw "Nie mozna sprawdzic stanu repozytorium." }
  if ($zmiany) {
    throw "Katalog ma niezapisane zmiany. Wydanie wymaga czystego repozytorium; zapisz zmiany albo uzyj osobnego klona."
  }
  git fetch origin master
  if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie pobrac origin/master." }
  git switch master
  if ($LASTEXITCODE -ne 0) { throw "Nie mozna przejsc na master; sprawdz lokalne galezie." }
  git merge --ff-only origin/master
  if ($LASTEXITCODE -ne 0) { throw "Lokalny master nie moze byc zaktualizowany fast-forward." }
  $tag = (git rev-parse --short=12 HEAD).Trim()
  Write-Host "== NotarAI produkcja - commit $tag" -ForegroundColor Cyan
  $tozsamosc = & aws sts get-caller-identity --profile $Profil --region $Region --query Account --output text
  if ($LASTEXITCODE -ne 0) {
    throw "Brak sesji AWS. Uruchom aws login --profile $Profil --region $Region i powtorz."
  }
  if ($tozsamosc.Trim() -ne "127621462971") {
    throw "Nieprawidlowe konto AWS. Wymagane konto produkcyjne NotarAI."
  }
  & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "2-zbuduj-obraz.ps1") -Profil $Profil -Region $Region
  if ($LASTEXITCODE -ne 0) { throw "Budowa obrazu nie powiodla sie." }
  & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "3-wdroz-aplikacje.ps1") -Profil $Profil -Region $Region -Tag $tag
  if ($LASTEXITCODE -ne 0) { throw "Wdrozenie aplikacji nie powiodlo sie." }
  # Po CloudFormation ALB moze jeszcze przepinac kontenery; weryfikacja trasy
  # zapobiega podaniu klientom linku do niesprawdzonej wersji.
  $portal = "https://app.notarai.pl/hurtowe"
  $gotowe = $false
  for($n=0; $n -lt 12; $n++) {
    try {
      $odp = Invoke-WebRequest -UseBasicParsing -Uri $portal -TimeoutSec 15
      if ($odp.StatusCode -eq 200 -and $odp.Content -match "Otworz terminarz|Otwórz terminarz") {
        $gotowe = $true
        break
      }
    } catch { }
    Start-Sleep -Seconds 10
  }
  if (-not $gotowe) {
    throw "Portal $portal nie odpowiada nowa wersja. Zatrzymano przed publikacja strony marketingowej."
  }
  Write-Host "== Portal B2B odpowiada poprawnie" -ForegroundColor Green
  if (-not $BezStrony) {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "strona.ps1") -Polecenie wyslij
    if ($LASTEXITCODE -ne 0) { throw "Publikacja notarai.pl przez FTPS nie powiodla sie." }
    $witryna = Invoke-WebRequest -UseBasicParsing -Uri "https://notarai.pl/?wydanie=$tag" -TimeoutSec 30
    if ($witryna.StatusCode -ne 200 -or $witryna.Content -notmatch "app.notarai.pl/hurtowe") {
      throw "Po wyslaniu strony nie potwierdzono linku do rezerwacji. Sprawdz cache hostingu i kopie FTPS."
    }
    Write-Host "== Strona notarai.pl z rezerwacjami B2B opublikowana" -ForegroundColor Green
  }
  Write-Host "== GOTOWE: commit $tag, portal $portal" -ForegroundColor Green
} finally {
  Pop-Location
}
