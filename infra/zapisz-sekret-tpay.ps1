# notarai - zapisuje klucze Tpay w Secrets Manager (sekret notarai/tpay)
#
# Uruchom z katalogu notarai:
#   powershell -ExecutionPolicy Bypass -File infra\zapisz-sekret-tpay.ps1
#
# Client secret wpisujesz w okno terminala - nie widac go na ekranie, nie
# trafia do historii PowerShella ani do argumentow polecenia aws (te widac
# na liscie procesow). Na chwile lezy w pliku tymczasowym dostepnym tylko
# dla Ciebie i jest kasowany zaraz po wyslaniu.
#
# Ponowne uruchomienie podmienia klucze (nowa wersja sekretu). Aplikacja
# wezmie je przy nastepnym wdrozeniu (3-wdroz-aplikacje.ps1).
param(
    [string]$Profil   = "notarai-admin",
    [string]$Region   = "eu-central-1",
    [string]$Konto    = "127621462971",
    [string]$ClientId = "01K8JX9V6JXA9WGXJ1RDM8YNE7-01M5NBCCBS4R6AXAMHXDW9QVW3"
)
$ErrorActionPreference = "Stop"
$Nazwa = "notarai/tpay"

function Czy-Aws {
    $ErrorActionPreference = "Continue"
    & aws @args --profile $Profil --region $Region 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

if (-not (Czy-Aws sts get-caller-identity)) {
    throw "Sesja profilu $Profil nie dziala. Odnow ja poleceniem:`n  aws login --profile $Profil --region $Region"
}
$biezace = & aws sts get-caller-identity --query Account --output text --profile $Profil --region $Region
if ($biezace -ne $Konto) { throw "Profil $Profil wskazuje konto $biezace, oczekiwane $Konto. Przerywam." }

Write-Host "Client ID: $ClientId"
$bezpieczny = Read-Host "Wklej client secret z panelu Tpay (nie bedzie widoczny)" -AsSecureString
$wskaznik = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($bezpieczny)
$plik = Join-Path $env:TEMP ("notarai-tpay-" + [guid]::NewGuid().ToString("N") + ".json")
try {
    $secret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($wskaznik).Trim()
    if ($secret.Length -lt 8) { throw "Client secret wyglada na pusty albo za krotki. Nic nie zapisalem." }

    # Plik tylko dla biezacego uzytkownika, bez BOM (aws czyta go jako tekst).
    New-Item -ItemType File -Path $plik | Out-Null
    $acl = Get-Acl $plik
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        [Security.Principal.WindowsIdentity]::GetCurrent().Name, "FullControl", "Allow")))
    Set-Acl $plik $acl
    $json = @{ client_id = $ClientId; client_secret = $secret } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($plik, $json, (New-Object Text.UTF8Encoding($false)))
    $secret = $null; $json = $null

    $wartosc = "file://" + $plik.Replace("\", "/")
    if (Czy-Aws secretsmanager describe-secret --secret-id $Nazwa) {
        & aws secretsmanager put-secret-value --secret-id $Nazwa --secret-string $wartosc `
            --profile $Profil --region $Region --query VersionId --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie podmienic sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Podmieniono klucze w sekrecie $Nazwa" -ForegroundColor Green
    } else {
        & aws secretsmanager create-secret --name $Nazwa `
            --description "notarai - klucze Tpay Open API (client_id, client_secret)" `
            --secret-string $wartosc --tags "Key=projekt,Value=notarai" `
            --profile $Profil --region $Region --query ARN --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie zalozyc sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Zalozono sekret $Nazwa w regionie $Region" -ForegroundColor Green
    }
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($wskaznik)
    if (Test-Path $plik) { Remove-Item $plik -Force }
}
Write-Host "Teraz wdroz aplikacje: infra\2-zbuduj-obraz.ps1, potem infra\3-wdroz-aplikacje.ps1"
