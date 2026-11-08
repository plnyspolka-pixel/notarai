# Publikacja ZMIENIONYCH plikow sekcji rezerwacji B2B na notarai.pl.
# Nie wymaga Pythona, py, instalacji dodatkowych bibliotek ani nowego logowania.
# Uzywa istniejacego profilu AWS i FTPS (TLS) w Windows PowerShell 5.1.
# Wysyla TYLKO strona/index.html i strona/brand-site.css.
# Nie generuje ani nie zmienia katalogu kancelarii / SEO / bloga.
param(
    [string]$Profil = "notarai-admin",
    [string]$Region = "eu-central-1"
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot
$strona = Join-Path $korzen "strona"
$pliki = @("index.html", "brand-site.css")
$hostFtps = "hosting2699662.online.pro"
$loginFtps = "notaraistrona@notarai.pl"

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "Brak AWS CLI. Ta publikacja potrzebuje juz skonfigurowanego polecenia aws."
}
if ([Environment]::Version.Major -ge 5) {
    throw "Ten skrypt jest dla Windows PowerShell 5.1 (.NET Framework); uruchom powershell.exe."
}
foreach ($plik in $pliki) {
    if (-not (Test-Path -LiteralPath (Join-Path $strona $plik) -PathType Leaf)) {
        throw "Nie znaleziono pliku: strona/$plik. Pobierz najnowszy master."
    }
}
$html = [IO.File]::ReadAllText((Join-Path $strona "index.html"), [Text.Encoding]::UTF8)
if ($html -notmatch 'id="hurtowe"' -or $html -notmatch 'https://app[.]notarai[.]pl/hurtowe') {
    throw "Strona nie zawiera sekcji B2B. Pobierz aktualny kod z master."
}

Write-Host "== Sprawdzam istniejacy profil AWS (bez logowania)" -ForegroundColor Cyan
$konto = & aws sts get-caller-identity --profile $Profil --region $Region --query Account --output text
if ($LASTEXITCODE -ne 0) {
    throw "Profil AWS $Profil nie dziala. Przerywam bez zmian na stronie."
}
if ($konto.Trim() -ne "127621462971") {
    throw "Nieprawidlowe konto AWS. Publikacja przerwana."
}

# Haslo pochodzi bezposrednio z AWS Secrets Manager. Nie zapisujemy go w pliku,
# nie przekazujemy w linii polecen i nie drukujemy w terminalu.
$sekretTekst = & aws secretsmanager get-secret-value --secret-id "notarai/strona-ftp" --profile $Profil --region $Region --query SecretString --output text
if ($LASTEXITCODE -ne 0 -or -not $sekretTekst) {
    throw "Nie udalo sie odczytac notarai/strona-ftp z AWS Secrets Manager."
}
$sekret = $sekretTekst | ConvertFrom-Json
$haslo = [string]$sekret.password
$sekretTekst = $null
$sekret = $null
if (-not $haslo) { throw "Brak pola password w sekrecie notarai/strona-ftp." }
$credentials = [System.Net.NetworkCredential]::new($loginFtps, $haslo)
$haslo = $null

function Utworz-ZadanieFtps([string]$Plik, [string]$Metoda) {
    $url = "ftp://$hostFtps/$Plik"
    $zadanie = [System.Net.FtpWebRequest][System.Net.WebRequest]::Create($url)
    $zadanie.Credentials = $credentials
    $zadanie.Method = $Metoda
    $zadanie.EnableSsl = $true
    $zadanie.UsePassive = $true
    $zadanie.UseBinary = $true
    $zadanie.KeepAlive = $false
    $zadanie.Timeout = 90000
    $zadanie.ReadWriteTimeout = 90000
    return $zadanie
}

function Pobierz-Ftps([string]$ZdalnyPlik, [string]$LokalnyPlik) {
    $zadanie = Utworz-ZadanieFtps $ZdalnyPlik ([System.Net.WebRequestMethods+Ftp]::DownloadFile)
    $odpowiedz = $zadanie.GetResponse()
    try {
        $zdalnyStrumien = $odpowiedz.GetResponseStream()
        try {
            $lokalnyStrumien = [System.IO.File]::Create($LokalnyPlik)
            try { $zdalnyStrumien.CopyTo($lokalnyStrumien) }
            finally { $lokalnyStrumien.Dispose() }
        } finally { $zdalnyStrumien.Dispose() }
    } finally { $odpowiedz.Close() }
}


function Lista-Ftps([string]$Katalog) {
    # Wiele serwerow az.pl udostepnia pliki pod public_html/ lub www/,
    # nie w katalogu startowym konta FTP.
    $zadanie = Utworz-ZadanieFtps $Katalog ([System.Net.WebRequestMethods+Ftp]::ListDirectory)
    $odpowiedz = $zadanie.GetResponse()
    try {
        $czytnik = [System.IO.StreamReader]::new($odpowiedz.GetResponseStream(), [System.Text.Encoding]::UTF8)
        try {
            $tresc = $czytnik.ReadToEnd()
        } finally { $czytnik.Dispose() }
    } finally { $odpowiedz.Close() }
    return @($tresc -split "\r?\n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -ne "." -and $_ -ne ".." })
}

function Zdalny-Plik([string]$Katalog, [string]$Plik) {
    if ([string]::IsNullOrEmpty($Katalog)) { return $Plik }
    return "$Katalog/$Plik"
}

function Znajdz-KatalogStrony([string]$KatalogKopii) {
    $kandydaci = [System.Collections.Generic.List[string]]::new()
    $kandydaci.Add("")
    $typowe = @("public_html", "www", "htdocs", "httpdocs", "html",
                "notarai.pl", "notarai.pl/public_html", "notarai.pl/www",
                "domains/notarai.pl/public_html")
    foreach ($k in $typowe) { $kandydaci.Add($k) }

    $listaKorzenia = @()
    try {
        $listaKorzenia = @(Lista-Ftps "")
        Write-Host "   Polaczono z FTPS. Wpisow w katalogu startowym: $($listaKorzenia.Count)"
        foreach ($pozycja in $listaKorzenia) {
            $nazwa = ($pozycja -replace '\\', '/').Split('/')[-1]
            if ($nazwa -match '^[a-zA-Z0-9_.-]{1,100}
    $zadanie = Utworz-ZadanieFtps $ZdalnyPlik ([System.Net.WebRequestMethods+Ftp]::UploadFile)
    $zadanie.ContentLength = ([System.IO.FileInfo]::new($LokalnyPlik)).Length
    $lokalnyStrumien = [System.IO.File]::OpenRead($LokalnyPlik)
    try {
        $zdalnyStrumien = $zadanie.GetRequestStream()
        try { $lokalnyStrumien.CopyTo($zdalnyStrumien) }
        finally { $zdalnyStrumien.Dispose() }
    } finally { $lokalnyStrumien.Dispose() }
    $odpowiedz = $zadanie.GetResponse()
    try {
        Write-Host "   FTPS: $ZdalnyPlik - $($odpowiedz.StatusDescription.Trim())"
    } finally { $odpowiedz.Close() }
}

$kopia = Join-Path $korzen ("strona-kopie\rezerwacje-" + (Get-Date -Format "yyyy-MM-dd-HHmmss"))
[void][System.IO.Directory]::CreateDirectory($kopia)
Write-Host "== Szukam katalogu strony na serwerze az.pl" -ForegroundColor Cyan
$katalogStrony = Znajdz-KatalogStrony $kopia
Write-Host "== Tworze kopie obu plikow strony w $kopia" -ForegroundColor Cyan
foreach ($plik in $pliki) {
    Pobierz-Ftps (Zdalny-Plik $katalogStrony $plik) (Join-Path $kopia $plik)
    Write-Host "   Kopia gotowa: $plik"
}
Write-Host "== Wysylam sekcje rezerwacji B2B" -ForegroundColor Cyan
foreach ($plik in $pliki) {
    Wyslij-Ftps (Join-Path $strona $plik) (Zdalny-Plik $katalogStrony $plik)
}

# Weryfikacja po FTPS, omija cache strony i sprawdza dokladna zawartosc.
Write-Host "== Sprawdzam sumy SHA256 pobranych plikow" -ForegroundColor Cyan
foreach ($plik in $pliki) {
    $sprawdzony = Join-Path $kopia ("po-wyslaniu-" + $plik)
    Pobierz-Ftps (Zdalny-Plik $katalogStrony $plik) $sprawdzony
    $zrodloHash = (Get-FileHash -LiteralPath (Join-Path $strona $plik) -Algorithm SHA256).Hash
    $serwerHash = (Get-FileHash -LiteralPath $sprawdzony -Algorithm SHA256).Hash
    if ($zrodloHash -ne $serwerHash) {
        throw "Weryfikacja $plik nie powiodla sie. Kopia poprzedniej wersji jest w $kopia."
    }
    Write-Host "   $plik - identyczny z serwerem" -ForegroundColor Green
}
Write-Host "== Gotowe. Pliki rezerwacji B2B sa na az.pl." -ForegroundColor Green
Write-Host "   https://notarai.pl/#hurtowe"
Write-Host "   Kopie poprzednich wersji: $kopia"
) {
                $kandydaci.Add($nazwa)
                if ($nazwa -match "^(notarai[.]pl|www|domains|public_html)$") {
                    $kandydaci.Add("$nazwa/public_html")
                    $kandydaci.Add("$nazwa/www")
                    $kandydaci.Add("$nazwa/notarai.pl")
                }
            }
        }
    } catch {
        Write-Host "   Serwer nie udostepnia listy katalogu startowego. Sprawdzam typowe sciezki." -ForegroundColor Yellow
    }

    $probkaIndex = Join-Path $KatalogKopii "probe-index.html"
    $probkaCss = Join-Path $KatalogKopii "probe-brand-site.css"
    foreach ($katalog in @($kandydaci | Select-Object -Unique | Select-Object -First 35)) {
        try {
            Pobierz-Ftps (Zdalny-Plik $katalog "index.html") $probkaIndex
            # Kandydat musi byc strona NotarAI, a nie inna witryna na tym samym koncie.
            $html = [System.IO.File]::ReadAllText($probkaIndex, [System.Text.Encoding]::UTF8)
            if ($html -notmatch '(?i)notarai' -or $html -notmatch 'app[.]notarai[.]pl') {
                continue
            }
            Pobierz-Ftps (Zdalny-Plik $katalog "brand-site.css") $probkaCss
            Write-Host "   Znalazlem katalog strony: /$katalog" -ForegroundColor Green
            return $katalog
        } catch {
            # PowerShell opakowuje FtpWebRequest.GetResponse (550) w
            # MethodInvocationException, a nie zawsze WebException.
            if ($_.Exception.ToString() -match '(^|[^0-9])550([^0-9]|$)') {
                continue
            }
            throw
        }
    }
    $wpisy = if ($listaKorzenia.Count -gt 0) {
        ($listaKorzenia | Select-Object -First 18) -join ", "
    } else { "(brak dostepnej listy)" }
    throw "Nie znaleziono katalogu strony NotarAI z index.html i brand-site.css. Wpisy FTP: $wpisy. Niczego nie wyslano."
}

function Wyslij-Ftps([string]$LokalnyPlik, [string]$ZdalnyPlik) {
    $zadanie = Utworz-ZadanieFtps $ZdalnyPlik ([System.Net.WebRequestMethods+Ftp]::UploadFile)
    $zadanie.ContentLength = ([System.IO.FileInfo]::new($LokalnyPlik)).Length
    $lokalnyStrumien = [System.IO.File]::OpenRead($LokalnyPlik)
    try {
        $zdalnyStrumien = $zadanie.GetRequestStream()
        try { $lokalnyStrumien.CopyTo($zdalnyStrumien) }
        finally { $zdalnyStrumien.Dispose() }
    } finally { $lokalnyStrumien.Dispose() }
    $odpowiedz = $zadanie.GetResponse()
    try {
        Write-Host "   FTPS: $ZdalnyPlik - $($odpowiedz.StatusDescription.Trim())"
    } finally { $odpowiedz.Close() }
}

$kopia = Join-Path $korzen ("strona-kopie\rezerwacje-" + (Get-Date -Format "yyyy-MM-dd-HHmmss"))
[void][System.IO.Directory]::CreateDirectory($kopia)
Write-Host "== Tworze kopie obu plikow strony w $kopia" -ForegroundColor Cyan
foreach ($plik in $pliki) {
    Pobierz-Ftps $plik (Join-Path $kopia $plik)
    Write-Host "   Kopia gotowa: $plik"
}
Write-Host "== Wysylam sekcje rezerwacji B2B" -ForegroundColor Cyan
foreach ($plik in $pliki) {
    Wyslij-Ftps (Join-Path $strona $plik) $plik
}

# Weryfikacja po FTPS, omija cache strony i sprawdza dokladna zawartosc.
Write-Host "== Sprawdzam sumy SHA256 pobranych plikow" -ForegroundColor Cyan
foreach ($plik in $pliki) {
    $sprawdzony = Join-Path $kopia ("po-wyslaniu-" + $plik)
    Pobierz-Ftps $plik $sprawdzony
    $zrodloHash = (Get-FileHash -LiteralPath (Join-Path $strona $plik) -Algorithm SHA256).Hash
    $serwerHash = (Get-FileHash -LiteralPath $sprawdzony -Algorithm SHA256).Hash
    if ($zrodloHash -ne $serwerHash) {
        throw "Weryfikacja $plik nie powiodla sie. Kopia poprzedniej wersji jest w $kopia."
    }
    Write-Host "   $plik - identyczny z serwerem" -ForegroundColor Green
}
Write-Host "== Gotowe. Pliki rezerwacji B2B sa na az.pl." -ForegroundColor Green
Write-Host "   https://notarai.pl/#hurtowe"
Write-Host "   Kopie poprzednich wersji: $kopia"
