# notarai.pl — pełna publikacja serwisu (katalog, blog, strony statyczne)
# Użycie:
#   powershell -ExecutionPolicy Bypass -File infra\strona.ps1 -Polecenie wyslij
#   powershell -ExecutionPolicy Bypass -File infra\strona.ps1 -Polecenie kopia
#   powershell -ExecutionPolicy Bypass -File infra\strona.ps1 -Polecenie lista
#
# Używa JUŻ AKTYWNEJ sesji AWS CLI (zmienne środowiskowe, AWS_PROFILE, SSO
# lub jawnie wskazany -Profil). Nie wykonuje logowania.
# Hasło FTPS jest pobierane z Secrets Manager i trafia tylko do środowiska
# procesu Pythona podczas połączenia; nigdy do linii poleceń lub logów.
# Bez Pythona NIE uruchamiamy automatycznie publikacji częściowej.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("lista", "kopia", "wyslij")]
    [string]$Polecenie,
    [string]$Profil = "",
    [string]$Region = "eu-central-1"
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot
$zrodlo = Join-Path $korzen "strona"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Pełna publikacja wymaga Python 3 (polecenie py -3). Nie wysyłam tylko dwóch plików zamiast całej strony. Dla samej sekcji B2B użyj świadomie infra\wyslij-rezerwacje-bez-pythona.ps1."
}
& py -3 --version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Launcher py jest dostępny, ale Python 3 nie uruchamia się." }
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "Brak AWS CLI. Wymagane jest istniejące połączenie do AWS Secrets Manager."
}

$awsOpcje = @("--region", $Region)
if ($Profil) { $awsOpcje += @("--profile", $Profil) }

# Ta kontrola nie loguje. Sesja w przeglądarce i sesja AWS CLI mogą być różne.
$konto = & aws sts get-caller-identity @awsOpcje --query Account --output text
if ($LASTEXITCODE -ne 0 -or -not $konto) {
    throw "Brak dostępu przez aktywną sesję AWS CLI. Nie zmieniono żadnych plików na serwerze."
}
if ($konto.Trim() -ne "127621462971") {
    throw "Błędne konto AWS ($konto); oczekiwano produkcyjnego konta NotarAI. Publikacja zatrzymana."
}

$bundle = Join-Path $env:USERPROFILE ".aws\ca-bundle.pem"
if (Test-Path -LiteralPath $bundle) { $env:SSL_CERT_FILE = $bundle }
$script:hasloFtps = $null

function Haslo-Ftps {
    if ($script:hasloFtps) { return $script:hasloFtps }
    # Sekret pobieramy bezpośrednio przez już skonfigurowane AWS CLI.
    # Zawartość nie jest wyświetlana i nie przechodzi przez AWS MCP.
    $tekst = & aws secretsmanager get-secret-value --secret-id "notarai/strona-ftp" @awsOpcje --query SecretString --output text
    if ($LASTEXITCODE -ne 0 -or -not $tekst) {
        throw "Nie mogę odczytać notarai/strona-ftp z Secrets Manager. Nie publikuję strony."
    }
    try { $sekret = $tekst | ConvertFrom-Json }
    catch { throw "Sekret notarai/strona-ftp nie jest poprawnym JSON-em." }
    $tekst = $null
    $haslo = [string]$sekret.password
    $sekret = $null
    if (-not $haslo) { throw "W sekrecie notarai/strona-ftp brakuje pola password." }
    $script:hasloFtps = $haslo
    return $script:hasloFtps
}

function Ftp([string[]]$argumenty) {
    $poprzednie = [Environment]::GetEnvironmentVariable("NOTARAI_FTP_HASLO", "Process")
    try {
        $env:NOTARAI_FTP_HASLO = Haslo-Ftps
        & py -3 -I (Join-Path $PSScriptRoot "strona_ftp.py") @argumenty
        if ($LASTEXITCODE -ne 0) {
            throw "FTPS $($argumenty[0]) nie powiódł się. Nie można uznać strony za opublikowaną."
        }
    } finally {
        if ($null -eq $poprzednie) {
            Remove-Item Env:NOTARAI_FTP_HASLO -ErrorAction SilentlyContinue
        } else {
            $env:NOTARAI_FTP_HASLO = $poprzednie
        }
    }
}

function Kopia {
    $cel = Join-Path $korzen ("strona-kopie\" + (Get-Date -Format "yyyy-MM-dd-HHmmss"))
    Write-Host "== Kopia plików serwera do $cel" -ForegroundColor Cyan
    Ftp @("kopia", "/", $cel)
}

switch ($Polecenie) {
    "lista" { Ftp @("lista", "/") }
    "kopia" { Kopia }
    "wyslij" {
        if (-not (Test-Path -LiteralPath (Join-Path $zrodlo "index.html") -PathType Leaf)) {
            throw "Brak strona\index.html. Uruchomienie przerwane."
        }
        # Offline: generujemy wyłącznie strony z katalogu i zatwierdzonych
        # poradników, bez automatycznego tworzenia nowych tekstów przez model.
        Write-Host "== Generuję katalog kancelarii i sitemap" -ForegroundColor Cyan
        & py -3 (Join-Path $korzen "seo\generuj.py")
        if ($LASTEXITCODE -ne 0) { throw "Generowanie katalogu i sitemap nie powiodło się." }
        Write-Host "== Generuję opublikowane artykuły" -ForegroundColor Cyan
        & py -3 (Join-Path $korzen "seo\blog.py") zbuduj
        if ($LASTEXITCODE -ne 0) { throw "Generowanie bloga nie powiodło się." }
        foreach ($plik in @("notariusz\index.html", "blog\index.html", "sitemap.xml", "kalkulator\index.html")) {
            if (-not (Test-Path -LiteralPath (Join-Path $zrodlo $plik) -PathType Leaf)) {
                throw "Brak wymaganego pliku: strona\$plik."
            }
        }
        Kopia
        Write-Host "== Wysyłam pełną stronę na az.pl przez FTPS" -ForegroundColor Cyan
        Ftp @("wyslij", $zrodlo, "/")
        Write-Host "== Pliki wysłane: https://notarai.pl" -ForegroundColor Green
    }
}
