# notarai - strona glowna notarai.pl na hostingu az.pl (hosting2699662, FTPS)
#
#   powershell -ExecutionPolicy Bypass -File infra\strona.ps1 lista
#   powershell -ExecutionPolicy Bypass -File infra\strona.ps1 kopia
#   powershell -ExecutionPolicy Bypass -File infra\strona.ps1 wyslij
#
# "wyslij" najpierw pobiera kopie tego, co jest na serwerze, do
# strona-kopie\<data-godzina>, a potem wysyla zawartosc katalogu strona\.
# Pliki, ktorych nie ma lokalnie, zostaja na serwerze.
#
# Haslo FTP jest w sekrecie notarai/strona-ftp (eu-central-1). asm-exec
# wstawia je do zmiennej srodowiskowej procesu Pythona - nie trafia do
# konsoli, logow ani repozytorium. Potrzebna sesja: aws login --profile notarai-admin
param(
    [Parameter(Mandatory = $true)][ValidateSet("lista", "kopia", "wyslij")][string]$Polecenie
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot
$zrodlo = Join-Path $korzen "strona"

$env:AWS_PROFILE = "notarai-admin"
$env:AWS_REGION = "eu-central-1"
$bundle = Join-Path $env:USERPROFILE ".aws\ca-bundle.pem"
if (Test-Path $bundle) { $env:SSL_CERT_FILE = $bundle }
$env:NOTARAI_FTP_HASLO = "{{resolve:secretsmanager:notarai/strona-ftp:SecretString:password}}"

function Ftp([string[]]$argumenty) {
    & py -3 -W ignore (Join-Path $PSScriptRoot "asm-exec.py") py -3 -I (Join-Path $PSScriptRoot "strona_ftp.py") @argumenty
    if ($LASTEXITCODE -ne 0) { throw "strona_ftp.py zakonczyl sie kodem $LASTEXITCODE" }
}

function Kopia {
    $cel = Join-Path $korzen ("strona-kopie\" + (Get-Date -Format "yyyy-MM-dd-HHmmss"))
    Write-Host "== Kopia serwera do $cel"
    Ftp @("kopia", "/", $cel)
}

switch ($Polecenie) {
    "lista" { Ftp @("lista", "/") }
    "kopia" { Kopia }
    "wyslij" {
        if (-not (Test-Path (Join-Path $zrodlo "index.html"))) { throw "Brak $zrodlo\index.html" }
        # Generujemy katalog kancelarii i tylko zatwierdzone artykuly przed kopia + FTPS.
        # Nie piszemy nowych artykulow modelem w czasie wdrozenia.
        Write-Host "== Buduje strony miast, katalog i sitemap"
        & py -3 (Join-Path $korzen "seo\generuj.py")
        if ($LASTEXITCODE -ne 0) { throw "Generowanie stron kancelarii nie powiodlo sie." }
        Write-Host "== Buduje opublikowane poradniki"
        & py -3 (Join-Path $korzen "seo\blog.py") zbuduj
        if ($LASTEXITCODE -ne 0) { throw "Generowanie bloga nie powiodlo sie." }
        foreach ($sciezka in @("notariusz\index.html", "blog\index.html", "sitemap.xml", "kalkulator\index.html")) {
            if (-not (Test-Path (Join-Path $zrodlo $sciezka))) { throw "Brak wygenerowanego pliku: $sciezka" }
        }
        Kopia
        Write-Host "== Wysylam $zrodlo"
        Ftp @("wyslij", $zrodlo, "/")
        Write-Host "== Gotowe: https://notarai.pl"
    }
}
