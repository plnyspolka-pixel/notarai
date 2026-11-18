# notarai - zapisuje dane aplikacji OAuth do podpinania skrzynek kancelarii
# (Microsoft 365 / Outlook i Google) w Secrets Manager: sekret notarai/oauth-poczty
#
# Uruchom (z dowolnego katalogu):
#   powershell -ExecutionPolicy Bypass -File <katalog repo>\infra\zapisz-sekret-oauth-poczty.ps1
#
# Wczesniej zarejestruj aplikacje (szczegoly: SAAS.md, "Poczta e-mail do spraw"):
# - Microsoft Entra (portal.azure.com -> App registrations): konta w dowolnej
#   organizacji i osobiste konta Microsoft, adres przekierowania (Web)
#   https://app.notarai.pl/api/korespondencja/oauth/powrot, uprawnienie
#   delegowane Office 365 Exchange Online -> IMAP.AccessAsUser.All, sekret klienta.
# - Google Cloud (APIs & Services -> Credentials): OAuth client typu Web
#   application, ten sam adres przekierowania, zakres https://mail.google.com/.
# Ktoregos dostawcy mozesz nie podawac (Enter) - jego przycisku po prostu nie bedzie.
# Wartosci wpisujesz w okno terminala - nie widac ich, nie trafiaja do historii.
# Aplikacja wezmie je przy nastepnym wdrozeniu (3-wdroz-aplikacje.ps1).
param(
    [string]$Profil = "notarai-admin",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971"
)
$ErrorActionPreference = "Stop"
$Nazwa = "notarai/oauth-poczty"

function Czy-Aws {
    $ErrorActionPreference = "Continue"
    & aws @args --profile $Profil --region $Region 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Wczytaj-Ukryty($pytanie) {
    $bezpieczny = Read-Host $pytanie -AsSecureString
    $wskaznik = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($bezpieczny)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($wskaznik).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($wskaznik) }
}

if (-not (Czy-Aws sts get-caller-identity)) {
    throw "Sesja profilu $Profil nie dziala. Odnow ja poleceniem:`n  aws login --profile $Profil --region $Region"
}
$biezace = & aws sts get-caller-identity --query Account --output text --profile $Profil --region $Region
if ($biezace -ne $Konto) { throw "Profil $Profil wskazuje konto $biezace, oczekiwane $Konto. Przerywam." }

$msKlient = (Read-Host "Microsoft: Application (client) ID (Enter = pomin)").Trim()
$msSekret = if ($msKlient) { Wczytaj-Ukryty "Microsoft: sekret klienta (nie bedzie widoczny)" } else { "" }
$gKlient = (Read-Host "Google: Client ID (Enter = pomin)").Trim()
$gSekret = if ($gKlient) { Wczytaj-Ukryty "Google: Client secret (nie bedzie widoczny)" } else { "" }
if (-not $msKlient -and -not $gKlient) { throw "Nie podano zadnej aplikacji. Nic nie zapisalem." }
if ($msKlient -and $msKlient -notmatch '^[0-9a-fA-F-]{36}$') { throw "Client ID Microsoft to GUID (36 znakow). Nic nie zapisalem." }
if ($gKlient -and $gKlient -notmatch '\.apps\.googleusercontent\.com$') { throw "Client ID Google konczy sie na .apps.googleusercontent.com. Nic nie zapisalem." }

$plik = Join-Path $env:TEMP ("notarai-oauth-" + [guid]::NewGuid().ToString("N") + ".json")
try {
    New-Item -ItemType File -Path $plik | Out-Null
    $acl = Get-Acl $plik
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        [Security.Principal.WindowsIdentity]::GetCurrent().Name, "FullControl", "Allow")))
    Set-Acl $plik $acl
    # Zawsze wszystkie cztery klucze (ECS wymaga kazdego, do ktorego odwoluje sie szablon).
    $json = @{ ms_klient = $msKlient; ms_sekret = $msSekret; google_klient = $gKlient; google_sekret = $gSekret } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($plik, $json, (New-Object Text.UTF8Encoding($false)))
    $msSekret = $null; $gSekret = $null; $json = $null

    $wartosc = "file://" + $plik.Replace("\", "/")
    if (Czy-Aws secretsmanager describe-secret --secret-id $Nazwa) {
        & aws secretsmanager put-secret-value --secret-id $Nazwa --secret-string $wartosc `
            --profile $Profil --region $Region --query VersionId --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie podmienic sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Podmieniono dane OAuth w sekrecie $Nazwa" -ForegroundColor Green
    } else {
        & aws secretsmanager create-secret --name $Nazwa `
            --description "notarai - aplikacje OAuth do podpinania skrzynek kancelarii (Microsoft, Google)" `
            --secret-string $wartosc --tags "Key=projekt,Value=notarai" `
            --profile $Profil --region $Region --query ARN --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie zalozyc sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Zalozono sekret $Nazwa w regionie $Region" -ForegroundColor Green
    }
} finally {
    if (Test-Path $plik) { Remove-Item $plik -Force }
}
Write-Host "Teraz wdroz aplikacje: infra\3-wdroz-aplikacje.ps1 (obraz bez zmian kodu nie wymaga przebudowy)"
