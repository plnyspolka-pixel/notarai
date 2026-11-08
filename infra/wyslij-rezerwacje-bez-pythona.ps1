# NotarAI — tylko sekcja B2B na az.pl, bez Pythona (Windows PowerShell 5.1)
# Pełną stronę, blog i katalog publikuje infra/strona.ps1.
# Ta operacja wysyła wyłącznie strona/index.html oraz strona/brand-site.css.
# Wykorzystuje aktywną sesję AWS CLI; nie wywołuje aws login.
param(
    [string]$Profil = "",
    [string]$Region = "eu-central-1"
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot
$strona = Join-Path $korzen "strona"
$pliki = @("index.html", "brand-site.css")
$hostFtps = "hosting2699662.online.pro"
$loginFtps = "notaraistrona@notarai.pl"

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "Brak AWS CLI — bezpieczne pobranie hasła FTP jest niemożliwe."
}
if ([Environment]::Version.Major -ge 5) {
    throw "Uruchom ten skrypt przez Windows PowerShell 5.1 (powershell.exe)."
}
foreach ($plik in $pliki) {
    if (-not (Test-Path -LiteralPath (Join-Path $strona $plik) -PathType Leaf)) {
        throw "Brak pliku strona/$plik."
    }
}
$html = [System.IO.File]::ReadAllText((Join-Path $strona "index.html"), [System.Text.Encoding]::UTF8)
if ($html -notmatch 'id="hurtowe"' -or $html -notmatch 'https://app[.]notarai[.]pl/hurtowe') {
    throw "Strona nie zawiera sekcji rezerwacji B2B — nie publikuję jej."
}

$awsOpcje = @("--region", $Region)
if ($Profil) { $awsOpcje += @("--profile", $Profil) }
$konto = & aws sts get-caller-identity @awsOpcje --query Account --output text
if ($LASTEXITCODE -ne 0 -or -not $konto -or $konto.Trim() -ne "127621462971") {
    throw "Brak aktywnego dostępu AWS CLI do konta produkcyjnego NotarAI."
}
$sekretTekst = & aws secretsmanager get-secret-value --secret-id "notarai/strona-ftp" @awsOpcje --query SecretString --output text
if ($LASTEXITCODE -ne 0 -or -not $sekretTekst) {
    throw "Nie mogę odczytać hasła FTPS z AWS Secrets Manager."
}
try { $sekret = $sekretTekst | ConvertFrom-Json }
catch { throw "Niepoprawny JSON w sekrecie notarai/strona-ftp." }
$haslo = [string]$sekret.password
$sekretTekst = $null
$sekret = $null
if (-not $haslo) { throw "Brak pola password w sekrecie FTP." }
$credentials = New-Object System.Net.NetworkCredential($loginFtps, $haslo)
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
        $zdalny = $odpowiedz.GetResponseStream()
        try {
            $lokalny = [System.IO.File]::Create($LokalnyPlik)
            try { $zdalny.CopyTo($lokalny) }
            finally { $lokalny.Dispose() }
        } finally { $zdalny.Dispose() }
    } finally { $odpowiedz.Close() }
}

function Lista-Ftps([string]$Katalog) {
    $zadanie = Utworz-ZadanieFtps $Katalog ([System.Net.WebRequestMethods+Ftp]::ListDirectory)
    $odpowiedz = $zadanie.GetResponse()
    try {
        $czytnik = New-Object System.IO.StreamReader($odpowiedz.GetResponseStream(), [System.Text.Encoding]::UTF8)
        try { $tresc = $czytnik.ReadToEnd() }
        finally { $czytnik.Dispose() }
    } finally { $odpowiedz.Close() }
    return @($tresc -split "\r?\n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -ne "." -and $_ -ne ".." })
}

function Zdalny-Plik([string]$Katalog, [string]$Plik) {
    if ([string]::IsNullOrEmpty($Katalog)) { return $Plik }
    return "$Katalog/$Plik"
}

function Znajdz-KatalogStrony([string]$KatalogKopii) {
    $kandydaci = New-Object System.Collections.Generic.List[string]
    $kandydaci.Add("")
    foreach ($k in @("public_html", "www", "htdocs", "httpdocs", "html",
                     "notarai.pl", "notarai.pl/public_html", "notarai.pl/www",
                     "domains/notarai.pl/public_html")) {
        $kandydaci.Add($k)
    }
    try {
        $listaKorzenia = @(Lista-Ftps "")
        foreach ($pozycja in $listaKorzenia) {
            $nazwa = (($pozycja -replace '\\', '/') -split '/')[-1]
            if ($nazwa -match '^[a-zA-Z0-9_.-]{1,100}$') {
                $kandydaci.Add($nazwa)
                if ($nazwa -match '^(notarai[.]pl|www|domains|public_html)$') {
                    $kandydaci.Add("$nazwa/public_html")
                    $kandydaci.Add("$nazwa/www")
                    $kandydaci.Add("$nazwa/notarai.pl")
                }
            }
        }
    } catch {
        Write-Host "Katalog startowy FTPS nie pozwala na listowanie; sprawdzam typowe katalogi." -ForegroundColor Yellow
    }

    $probkaIndex = Join-Path $KatalogKopii "probe-index.html"
    $probkaCss = Join-Path $KatalogKopii "probe-brand-site.css"
    foreach ($katalog in @($kandydaci | Select-Object -Unique | Select-Object -First 35)) {
        try {
            Pobierz-Ftps (Zdalny-Plik $katalog "index.html") $probkaIndex
            $htmlProbka = [System.IO.File]::ReadAllText($probkaIndex, [System.Text.Encoding]::UTF8)
            if ($htmlProbka -notmatch '(?i)notarai' -or $htmlProbka -notmatch 'app[.]notarai[.]pl') {
                continue
            }
            Pobierz-Ftps (Zdalny-Plik $katalog "brand-site.css") $probkaCss
            Write-Host "FTPS: znaleziono stronę NotarAI w /$katalog" -ForegroundColor Green
            return $katalog
        } catch {
            # 550 to typowy kod braku pliku w sprawdzanym katalogu.
            if ($_.Exception.ToString() -match '(^|[^0-9])550([^0-9]|$)') { continue }
            throw
        }
    }
    throw "Nie znaleziono właściwego katalogu NotarAI z index.html i brand-site.css. Niczego nie wysłano."
}

function Wyslij-Ftps([string]$LokalnyPlik, [string]$ZdalnyPlik) {
    $zadanie = Utworz-ZadanieFtps $ZdalnyPlik ([System.Net.WebRequestMethods+Ftp]::UploadFile)
    $zadanie.ContentLength = (Get-Item -LiteralPath $LokalnyPlik).Length
    $wejscie = [System.IO.File]::OpenRead($LokalnyPlik)
    try {
        $zdalny = $zadanie.GetRequestStream()
        try { $wejscie.CopyTo($zdalny) }
        finally { $zdalny.Dispose() }
    } finally { $wejscie.Dispose() }
    $odpowiedz = $zadanie.GetResponse()
    try { Write-Host "FTPS: $ZdalnyPlik — $($odpowiedz.StatusDescription.Trim())" }
    finally { $odpowiedz.Close() }
}

$kopia = Join-Path $korzen ("strona-kopie\rezerwacje-" + (Get-Date -Format "yyyy-MM-dd-HHmmss"))
[void][System.IO.Directory]::CreateDirectory($kopia)
$katalogStrony = Znajdz-KatalogStrony $kopia
Write-Host "== Kopia obu plików do $kopia" -ForegroundColor Cyan
foreach ($plik in $pliki) {
    Pobierz-Ftps (Zdalny-Plik $katalogStrony $plik) (Join-Path $kopia $plik)
}
Write-Host "== Publikuję tylko sekcję rezerwacji B2B" -ForegroundColor Cyan
foreach ($plik in $pliki) {
    Wyslij-Ftps (Join-Path $strona $plik) (Zdalny-Plik $katalogStrony $plik)
}
foreach ($plik in $pliki) {
    $sprawdzony = Join-Path $kopia ("po-wyslaniu-" + $plik)
    Pobierz-Ftps (Zdalny-Plik $katalogStrony $plik) $sprawdzony
    $lokalnyHash = (Get-FileHash -LiteralPath (Join-Path $strona $plik) -Algorithm SHA256).Hash
    $serwerHash = (Get-FileHash -LiteralPath $sprawdzony -Algorithm SHA256).Hash
    if ($lokalnyHash -ne $serwerHash) {
        throw "Niezgodność SHA256 dla $plik. Poprzednia wersja znajduje się w $kopia."
    }
}
Write-Host "== Gotowe: https://notarai.pl/#hurtowe" -ForegroundColor Green
Write-Host "Kopie poprzednich wersji: $kopia"
