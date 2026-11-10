# notarai - zapisuje dane konta Twilio w Secrets Manager (sekret notarai/twilio)
#
# Uruchom (z dowolnego katalogu):
#   powershell -ExecutionPolicy Bypass -File <katalog repo>\infra\zapisz-sekret-twilio.ps1
#
# Wlacza SMS do klientow aplikacji notarai (sms.py): kod weryfikacyjny,
# potwierdzenie i przypomnienie wizyty, a tym samym rezerwacje online
# (rezerwacje_klienta.py, docs/aplikacja-klienta.md).
#
# OSOBNE konto albo podkonto Twilio i osobny numer od Finance You: numer ma
# jeden webhook, wspolny kierowalby odpowiedzi klientow kancelarii do systemu
# pozyczkowego. W konsoli Twilio ustaw dla tego numeru:
#   Messaging -> A MESSAGE COMES IN -> Webhook, HTTP POST
#   https://app.notarai.pl/api/klient/sms-przychodzacy?token=<token webhooka>
#
# Wartosci wpisujesz w okno terminala - nie widac ich na ekranie, nie trafiaja
# do historii PowerShella ani do argumentow polecenia aws. Ponowne uruchomienie
# podmienia sekret (nowa wersja). Aplikacja wezmie go przy nastepnym wdrozeniu
# (3-wdroz-aplikacje.ps1). Zeby wylaczyc SMS: usun sekret
#   aws secretsmanager delete-secret --secret-id notarai/twilio
# i wdroz ponownie - aplikacja przelaczy sie na PIECZAPP_SMS_TRYB=wylaczony.
param(
    [string]$Profil = "notarai-admin",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971"
)
$ErrorActionPreference = "Stop"
$Nazwa = "notarai/twilio"

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

$sid = Wczytaj-Ukryty "Account SID podkonta Twilio dla notarai (AC..., nie bedzie widoczny)"
if ($sid -notmatch '^AC[0-9a-fA-F]{32}$') { throw "Account SID to 'AC' i 32 znaki szesnastkowe. Nic nie zapisalem." }
$token = Wczytaj-Ukryty "Auth Token tego podkonta (nie bedzie widoczny)"
if ($token.Length -lt 32 -or $token -notmatch '^[A-Za-z0-9]+$') { throw "Auth Token powinien miec co najmniej 32 znaki. Nic nie zapisalem." }
$numer = (Read-Host "Numer nadawcy w formacie E.164, np. +48500000000 (osobny od Finance You)").Trim()
if ($numer -notmatch '^\+[1-9][0-9]{7,14}$') { throw "Numer podaj jako +48... (E.164). Nic nie zapisalem." }
$webhook = (Read-Host "Token webhooka odpowiedzi SMS (Enter = wygeneruj losowy)").Trim()
if (-not $webhook) {
    $bajty = New-Object byte[] 24
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bajty)
    $webhook = ([Convert]::ToBase64String($bajty)) -replace '[^A-Za-z0-9]', ''
}
if ($webhook.Length -lt 16 -or $webhook -notmatch '^[A-Za-z0-9_\-]+$') { throw "Token webhooka: co najmniej 16 znakow (litery, cyfry, - i _)." }

$plik = Join-Path $env:TEMP ("notarai-twilio-" + [guid]::NewGuid().ToString("N") + ".json")
try {
    New-Item -ItemType File -Path $plik | Out-Null
    $acl = Get-Acl $plik
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        [Security.Principal.WindowsIdentity]::GetCurrent().Name, "FullControl", "Allow")))
    Set-Acl $plik $acl
    $json = @{ account_sid = $sid; auth_token = $token; numer = $numer; webhook_token = $webhook } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($plik, $json, (New-Object Text.UTF8Encoding($false)))
    $sid = $null; $token = $null; $json = $null

    $wartosc = "file://" + $plik.Replace("\", "/")
    if (Czy-Aws secretsmanager describe-secret --secret-id $Nazwa) {
        & aws secretsmanager put-secret-value --secret-id $Nazwa --secret-string $wartosc `
            --profile $Profil --region $Region --query VersionId --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie podmienic sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Podmieniono dane Twilio w sekrecie $Nazwa" -ForegroundColor Green
    } else {
        & aws secretsmanager create-secret --name $Nazwa `
            --description "notarai - Twilio (SMS do klientow aplikacji: kod, potwierdzenie, przypomnienie)" `
            --secret-string $wartosc --tags "Key=projekt,Value=notarai" `
            --profile $Profil --region $Region --query ARN --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie zalozyc sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Zalozono sekret $Nazwa w regionie $Region" -ForegroundColor Green
    }
} finally {
    if (Test-Path $plik) { Remove-Item $plik -Force }
}
Write-Host "Webhook numeru w konsoli Twilio (HTTP POST):"
Write-Host "  https://app.notarai.pl/api/klient/sms-przychodzacy?token=$webhook"
Write-Host "Teraz wdroz aplikacje: infra\3-wdroz-aplikacje.ps1 (ustawi PIECZAPP_SMS_TRYB=twilio)"
