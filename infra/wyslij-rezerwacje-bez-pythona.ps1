# Bezpieczna publikacja sekcji B2B na istniejacej stronie notarai.pl.
# Bez Pythona, instalacji dodatkowych bibliotek i ponownego logowania AWS.
# Pobiera kopie index.html z FTPS, dodaje sekcje i lacze CSS, wysyla tylko:
#  - nowy plik rezerwacje-b2b.css
#  - zmodyfikowany zdalny index.html (bez nadpisywania innych sekcji)
# Nie zmienia style.css, katalogu kancelarii, SEO ani bloga.
param(
    [string]$Profil = "notarai-admin",
    [string]$Region = "eu-central-1"
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot
$strona = Join-Path $korzen "strona"
$plikCss = Join-Path $korzen "strona\rezerwacje-b2b.css"
$hostFtps = "hosting2699662.online.pro"
$loginFtps = "notaraistrona@notarai.pl"

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "Brak AWS CLI. Ta publikacja potrzebuje juz skonfigurowanego polecenia aws."
}
if ([Environment]::Version.Major -ge 5) {
    throw "Ten skrypt jest dla Windows PowerShell 5.1 (.NET Framework); uruchom powershell.exe."
}
if (-not (Test-Path -LiteralPath $plikCss -PathType Leaf)) { throw "Brak strona/rezerwacje-b2b.css. Pobierz master." }

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
    $zadanie = Utworz-ZadanieFtps $Katalog ([System.Net.WebRequestMethods+Ftp]::ListDirectory)
    $odpowiedz = $zadanie.GetResponse()
    try {
        $czytnik = [System.IO.StreamReader]::new($odpowiedz.GetResponseStream())
        try {
            $tresc = $czytnik.ReadToEnd()
        } finally {
            $czytnik.Dispose()
        }
    } finally {
        $odpowiedz.Close()
    }
    return @($tresc -split "\r?\n" | Where-Object { $_.Trim() -ne "" -and $_.Trim() -ne "." -and $_.Trim() -ne ".." })
}

function Zdalny-Plik([string]$Katalog, [string]$Plik) {
    if ([string]::IsNullOrEmpty($Katalog)) {
        return $Plik
    }
    return "$Katalog/$Plik"
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
$wpisy = @(Lista-Ftps "")
Write-Host "== Katalog FTPS: $($wpisy.Count) wpisow" -ForegroundColor Cyan
if ($wpisy -notcontains "index.html" -or $wpisy -notcontains "style.css") {
    throw "Nie rozpoznano katalogu domeny notarai.pl. Niczego nie wyslano."
}
$kopiaIndex = Join-Path $kopia "index.html"
Pobierz-Ftps "index.html" $kopiaIndex
$staryHtml = [System.IO.File]::ReadAllText($kopiaIndex,[System.Text.Encoding]::UTF8)
if ($staryHtml -notmatch '(?i)notarai' -or $staryHtml -notmatch 'app[.]notarai[.]pl') {
    throw "Nie rozpoznano index.html NotarAI. Niczego nie wyslano."
}
Write-Host "== Kopia oryginalnego index.html: $kopiaIndex" -ForegroundColor Green
if ($wpisy -contains "rezerwacje-b2b.css") {
    Pobierz-Ftps "rezerwacje-b2b.css" (Join-Path $kopia "rezerwacje-b2b.css")
}

$sekcja = @'
<!-- NOTARAI B2B BOOKING START -->
<section id="rezerwacje-b2b" class="sekcja" aria-labelledby="b2b-title">
  <div class="szer b2b-layout">
    <div class="b2b-copy">
      <span class="b2b-eyebrow">Nowosc - dla klientow hurtowych</span>
      <h2 id="b2b-title">Umawianie spotkan notarialnych przez API i MCP</h2>
      <p>Biura nieruchomosci, deweloperzy i firmy obslugujace wiele transakcji moga rezerwowac wizyty bez wymiany maili i telefonow. Kancelaria sama ustala dostepne terminy.</p>
      <div class="b2b-actions">
        <a class="b2b-button b2b-button-primary" href="https://app.notarai.pl/hurtowe">Otworz panel rezerwacji</a>
        <a class="b2b-button b2b-button-secondary" href="mailto:kontakt@notarai.pl?subject=Dostep%20B2B%20API%20MCP">Uzyskaj dostep B2B</a>
      </div>
      <p class="b2b-footnote">Dostep dla autoryzowanych firm z kluczem API.</p>
    </div>
    <div class="b2b-features">
      <div class="b2b-feature"><span class="b2b-number">01</span><div><strong>Wolne terminy</strong><p>Sprawdz godziny w udostepnionych kancelariach.</p></div></div>
      <div class="b2b-feature"><span class="b2b-number">02</span><div><strong>Potwierdzenie w kalendarzu</strong><p>Termin trafia bezposrednio do systemu notariusza.</p></div></div>
      <div class="b2b-feature"><span class="b2b-number">03</span><div><strong>REST API i agenci MCP</strong><p>Integracja z CRM, przekladanie i anulowanie wizyt.</p></div></div>
      <div class="b2b-feature"><span class="b2b-number">04</span><div><strong>Kontrola kancelarii</strong><p>Notariusz decyduje, jakie terminy udostepnia.</p></div></div>
    </div>
  </div>
</section>
<!-- NOTARAI B2B BOOKING END -->

'@
$nowyHtml = $staryHtml
if ($nowyHtml -notmatch 'id="rezerwacje-b2b"') {
    $miejsce = [regex]::Match($nowyHtml, '(?i)<section\s+id=["'']latwo["'']')
    if (-not $miejsce.Success) { throw "Brak sekcji latwo. Nie zmieniono strony." }
    $nowyHtml = $nowyHtml.Insert($miejsce.Index,$sekcja)
}
if ($nowyHtml -notmatch 'href="rezerwacje-b2b[.]css"') {
    if (-not $nowyHtml.Contains("</head>")) { throw "Brak head. Nie zmieniono strony." }
    $nowyHtml = $nowyHtml.Replace("</head>", '<link rel="stylesheet" href="rezerwacje-b2b.css">' + [Environment]::NewLine + "</head>")
}
if ($nowyHtml -notmatch 'href="#rezerwacje-b2b"') {
    $nav = $nowyHtml.IndexOf("</nav>")
    if ($nav -ge 0) {
        $nowyHtml = $nowyHtml.Insert($nav, '      <a href="#rezerwacje-b2b">Rezerwacje B2B</a>' + [Environment]::NewLine + "    ")
    }
}
if ($nowyHtml -notmatch 'https://app[.]notarai[.]pl/hurtowe') { throw "Brak linku B2B w wyniku." }
$nowyPlik = Join-Path $kopia "nowy-index.html"
[System.IO.File]::WriteAllText($nowyPlik,$nowyHtml,(New-Object System.Text.UTF8Encoding($false)))
$kontrolaPrzed = Join-Path $kopia "kontrola-przed.html"
Pobierz-Ftps "index.html" $kontrolaPrzed
if ((Get-FileHash $kopiaIndex -Algorithm SHA256).Hash -ne (Get-FileHash $kontrolaPrzed -Algorithm SHA256).Hash) {
    throw "index.html zmienil sie podczas operacji. Nie nadpisano obcych zmian."
}
Write-Host "== Wysylam nowy CSS, dotychczasowy style.css pozostaje bez zmian" -ForegroundColor Cyan
Wyslij-Ftps $plikCss "rezerwacje-b2b.css"
$kontrolaCss = Join-Path $kopia "kontrola-css.css"
Pobierz-Ftps "rezerwacje-b2b.css" $kontrolaCss
if ((Get-FileHash $plikCss -Algorithm SHA256).Hash -ne (Get-FileHash $kontrolaCss -Algorithm SHA256).Hash) {
    throw "Weryfikacja CSS nie powiodla sie. Index.html niezmieniony."
}
Write-Host "== Dodaje sekcje B2B do istniejacego index.html" -ForegroundColor Cyan
$proba = $false
try {
    $proba = $true
    Wyslij-Ftps $nowyPlik "index.html"
    $sprawdzenie = Join-Path $kopia "kontrola-po.html"
    Pobierz-Ftps "index.html" $sprawdzenie
    if ((Get-FileHash $nowyPlik -Algorithm SHA256).Hash -ne (Get-FileHash $sprawdzenie -Algorithm SHA256).Hash) {
        throw "Weryfikacja index.html po wyslaniu nie powiodla sie."
    }
} catch {
    $blad = $_.Exception.Message
    if ($proba) {
        Write-Host "== Proba przywrocenia poprzedniego index.html" -ForegroundColor Yellow
        try { Wyslij-Ftps $kopiaIndex "index.html" }
        catch { Write-Host "Blad przywracania. Kopia: $kopiaIndex" -ForegroundColor Red }
    }
    throw "Blad publikacji HTML: $blad"
}
Write-Host "== GOTOWE - sekcja B2B na FTPS az.pl" -ForegroundColor Green
Write-Host "   https://notarai.pl/#rezerwacje-b2b"
Write-Host "   Kopia strony: $kopiaIndex"
