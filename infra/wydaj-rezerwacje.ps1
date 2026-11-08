# NotarAI — produkcja z aktywnej sesji AWS CLI
#
# Z katalogu repozytorium w Windows PowerShell:
#   powershell -ExecutionPolicy Bypass -File infra\wydaj-rezerwacje.ps1
#   powershell -ExecutionPolicy Bypass -File infra\wydaj-rezerwacje.ps1 -BezStrony
#   powershell -ExecutionPolicy Bypass -File infra\wydaj-rezerwacje.ps1 -Profil notarai-admin
#
# Bez ponownego logowania: AWS_PROFILE/obecny kontekst CLI, następnie notarai-admin.
# Wymaga CodeBuild/ECR, CloudFormation/ECS, Secrets Manager i dla WWW Python 3.
param(
    [string]$Profil = "",
    [string]$Region = "eu-central-1",
    [switch]$BezStrony
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot
$kontoProdukcyjne = "127621462971"

function Konto-Aws([string]$Kandydat) {
    $ErrorActionPreference = "Continue"
    $argumenty = @("sts", "get-caller-identity", "--region", $Region, "--query", "Account", "--output", "text")
    if ($Kandydat) { $argumenty += @("--profile", $Kandydat) }
    $konto = & aws @argumenty 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $konto) { return "" }
    return ([string]$konto).Trim()
}

function Sprawdz-Http([string]$Url, [string]$Fragment, [int]$Proby = 12) {
    for ($nr = 0; $nr -lt $Proby; $nr++) {
        try {
            $separator = if ($Url.Contains("?")) { "&" } else { "?" }
            $adres = $Url + $separator + "notarai_wydanie=" + $tag
            $odp = Invoke-WebRequest -UseBasicParsing -Uri $adres -TimeoutSec 20 -Headers @{"Cache-Control" = "no-cache"}
            if ($odp.StatusCode -eq 200 -and ([string]$odp.Content).Contains($Fragment)) {
                return
            }
        } catch {
            # Nie drukujemy treści odpowiedzi serwera.
        }
        if ($nr -lt $Proby - 1) { Start-Sleep -Seconds 10 }
    }
    throw "Brak potwierdzenia nowej wersji pod adresem $Url (oczekiwany fragment: $Fragment)."
}

Push-Location $korzen
try {
    foreach ($narzedzie in @("git", "aws", "powershell")) {
        if (-not (Get-Command $narzedzie -ErrorAction SilentlyContinue)) {
            throw "Brak polecenia $narzedzie. Publikacja zatrzymana przed jakąkolwiek zmianą."
        }
    }
    if (-not $BezStrony) {
        if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
            throw "Pełne wydanie wymaga Python 3 (py -3). Nie wysyłam po cichu dwóch plików zamiast całej strony."
        }
        & py -3 --version | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie można uruchomić Python 3 poleceniem py -3." }
    }

    # Jawny -Profil ma pierwszeństwo. W innym przypadku korzystamy z obecnej
    # sesji AWS CLI (łącznie z AWS_PROFILE), bez wywoływania aws login.
    $kandydaci = @()
    if ($Profil) {
        $kandydaci = @($Profil)
    } else {
        if ($env:AWS_PROFILE) { $kandydaci += $env:AWS_PROFILE }
        $kandydaci += ""
        $kandydaci += "notarai-admin"
    }
    $wybranyProfil = ""
    $sesjaAktywna = $false
    foreach ($kandydat in ($kandydaci | Select-Object -Unique)) {
        if ((Konto-Aws $kandydat) -eq $kontoProdukcyjne) {
            $wybranyProfil = $kandydat
            $sesjaAktywna = $true
            break
        }
    }
    if (-not $sesjaAktywna) {
        throw "Brak sesji AWS CLI do produkcyjnego konta NotarAI. Niczego nie wdrożono. Zalogowana karta Chrome nie jest automatycznie sesją AWS CLI."
    }
    Write-Host "== AWS: aktywna sesja produkcyjna, bez ponownego logowania" -ForegroundColor Green

    $origin = & git remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $origin -notmatch '([/:])plnyspolka-pixel/notarai(\.git)?$') {
        throw "Katalog nie wskazuje na repozytorium plnyspolka-pixel/notarai."
    }
    $zmiany = @(git status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw "Nie można sprawdzić stanu Git." }
    if ($zmiany.Count -gt 0 -and ($zmiany -join "").Trim()) {
        throw "Są niezapisane zmiany. Nie przełączam gałęzi, nie usuwam plików. Zrób commit lub użyj czystego klona."
    }

    & git fetch origin master
    if ($LASTEXITCODE -ne 0) { throw "Nie można pobrać origin/master." }
    & git switch master
    if ($LASTEXITCODE -ne 0) { throw "Nie można przejść na master." }
    & git merge --ff-only origin/master
    if ($LASTEXITCODE -ne 0) { throw "Lokalny master różni się od GitHub. Nie wykonuję force-pull ani reset." }

    $tag = (& git rev-parse --short=12 HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $tag -notmatch '^[0-9a-f]{12}$') {
        throw "Nie można odczytać identyfikatora commita."
    }
    Write-Host "== NotarAI: wydanie commita $tag" -ForegroundColor Cyan

    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "2-zbuduj-obraz.ps1") -Profil $wybranyProfil -Region $Region
    if ($LASTEXITCODE -ne 0) { throw "Budowa obrazu ECR nie powiodła się." }
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "3-wdroz-aplikacje.ps1") -Profil $wybranyProfil -Region $Region -Tag $tag
    if ($LASTEXITCODE -ne 0) { throw "Wdrożenie ECS nie powiodło się." }

    # Read-only smoke tests przed publikacją nowej strony marketingowej.
    Sprawdz-Http "https://app.notarai.pl/hurtowe" "Otwórz terminarz" 18
    Sprawdz-Http "https://app.notarai.pl/notariusze" "/static/leaflet/leaflet.js" 6
    Sprawdz-Http "https://app.notarai.pl/kalkulator" "api/taksa" 6
    Write-Host "== Aplikacja: strony B2B, mapa i kalkulator odpowiadają" -ForegroundColor Green

    if (-not $BezStrony) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "strona.ps1") -Polecenie wyslij -Profil $wybranyProfil -Region $Region
        if ($LASTEXITCODE -ne 0) { throw "Publikacja FTPS nie powiodła się." }
        Sprawdz-Http "https://notarai.pl/" "https://app.notarai.pl/hurtowe" 6
        Sprawdz-Http "https://notarai.pl/kalkulator/" "api/taksa" 6
        Sprawdz-Http "https://notarai.pl/notariusz/" "notariusz" 6
        # Neutralne strony miejscowosci: przycisk rezerwacji ukryty, dopoki API nie potwierdzi
        # rezerwacji online; bez odznak i bez "dowolnej kancelarii".
        Sprawdz-Http "https://notarai.pl/notariusz/lublin/" "[hidden] { display: none !important; }" 6
        Sprawdz-Http "https://notarai.pl/kalkulator/" "w swojej okolicy" 6
        Write-Host "== Serwis, katalog i kalkulator potwierdzone" -ForegroundColor Green
    } else {
        Write-Host "== Pominięto aktualizację notarai.pl (-BezStrony)." -ForegroundColor Yellow
    }
    Write-Host "== GOTOWE: wdrożenie commita $tag potwierdzone" -ForegroundColor Green
} finally {
    Pop-Location
}
