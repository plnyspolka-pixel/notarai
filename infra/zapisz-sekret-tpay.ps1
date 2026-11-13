# notarai - zapisuje klucze TPay w Secrets Manager (sekret notarai/tpay)
#
# Uruchom (z dowolnego katalogu):
#   powershell -ExecutionPolicy Bypass -File C:\Users\Pieczak\notarai\infra\zapisz-sekret-tpay.ps1
#
# Skrypt pyta o trzy wartosci z panelu sprzedawcy TPay:
#   1. Client ID          Integracja -> API -> Klucze Open API -> Dodaj nowy klucz
#   2. Client Secret      pokazywany tylko raz, przy zakladaniu klucza
#   3. kod bezpieczenstwa Powiadomienia -> Bezpieczenstwo (dawniej "kod potwierdzajacy");
#                         z niego liczymy sume md5 kazdego powiadomienia o wplacie
# W panelu TPay ustaw tez adres powiadomien na https://app.notarai.pl/api/tpay/powiadomienie
# (aplikacja i tak podaje go przy kazdej transakcji).
# Wpisujesz je w okno terminala - nie widac ich na ekranie, nie trafiaja do
# historii PowerShella ani do argumentow polecenia aws (te widac na liscie
# procesow). Na chwile leza w pliku tymczasowym dostepnym tylko dla Ciebie
# i sa kasowane zaraz po wyslaniu.
#
# Ponowne uruchomienie podmienia klucze (nowa wersja sekretu). Aplikacja
# wezmie je przy nastepnym wdrozeniu (3-wdroz-aplikacje.ps1).
param(
    [string]$Profil = "notarai-admin",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971"
)
$ErrorActionPreference = "Stop"
$Nazwa = "notarai/tpay"

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

$clientId = Wczytaj-Ukryty "Wklej Client ID klucza Open API TPay (nie bedzie widoczny)"
if ($clientId -notmatch '^[A-Za-z0-9._-]{4,}$') { throw "To nie wyglada na Client ID TPay. Nic nie zapisalem." }
$clientSecret = Wczytaj-Ukryty "Wklej Client Secret (nie bedzie widoczny)"
if ($clientSecret.Length -lt 8) { throw "Client Secret jest za krotki. Nic nie zapisalem." }
$kod = Wczytaj-Ukryty "Wklej kod bezpieczenstwa powiadomien (nie bedzie widoczny)"
if ($kod.Length -lt 4) { throw "Kod bezpieczenstwa jest za krotki - bez niego nie sprawdzimy powiadomien. Nic nie zapisalem." }

$plik = Join-Path $env:TEMP ("notarai-tpay-" + [guid]::NewGuid().ToString("N") + ".json")
try {
    # Plik tylko dla biezacego uzytkownika, bez BOM (aws czyta go jako tekst).
    New-Item -ItemType File -Path $plik | Out-Null
    $acl = Get-Acl $plik
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        [Security.Principal.WindowsIdentity]::GetCurrent().Name, "FullControl", "Allow")))
    Set-Acl $plik $acl
    $json = @{ client_id = $clientId; client_secret = $clientSecret; kod = $kod } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($plik, $json, (New-Object Text.UTF8Encoding($false)))
    $clientId = $null; $clientSecret = $null; $kod = $null; $json = $null

    $wartosc = "file://" + $plik.Replace("\", "/")
    if (Czy-Aws secretsmanager describe-secret --secret-id $Nazwa) {
        & aws secretsmanager put-secret-value --secret-id $Nazwa --secret-string $wartosc `
            --profile $Profil --region $Region --query VersionId --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie podmienic sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Podmieniono klucze w sekrecie $Nazwa" -ForegroundColor Green
    } else {
        & aws secretsmanager create-secret --name $Nazwa `
            --description "notarai - klucze TPay (Open API i kod bezpieczenstwa powiadomien)" `
            --secret-string $wartosc --tags "Key=projekt,Value=notarai" `
            --profile $Profil --region $Region --query ARN --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie zalozyc sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Zalozono sekret $Nazwa w regionie $Region" -ForegroundColor Green
    }
} finally {
    if (Test-Path $plik) { Remove-Item $plik -Force }
}
Write-Host "Teraz wdroz aplikacje: infra\2-zbuduj-obraz.ps1, potem infra\3-wdroz-aplikacje.ps1"
