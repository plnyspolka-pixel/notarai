# notarai - zapisuje token Apify w Secrets Manager (sekret notarai/apify)
#
# Uruchom (z dowolnego katalogu):
#   powershell -ExecutionPolicy Bypass -File <katalog repo>\infra\zapisz-sekret-apify.ps1
#
# Token wlacza pobieranie tresci ksiag wieczystych z EKW przez aktora
# regdata/ekw-ksiegi-wieczyste-scraper (ekw.py, docs/rejestry.md). Znajdziesz
# go w konsoli Apify: Settings -> API & Integrations -> Personal API tokens.
# Wpisujesz go w okno terminala - nie widac go na ekranie, nie trafia do
# historii PowerShella ani do argumentow polecenia aws. Na chwile lezy w pliku
# tymczasowym dostepnym tylko dla Ciebie i jest kasowany zaraz po wyslaniu.
#
# Ponowne uruchomienie podmienia token (nowa wersja sekretu). Aplikacja wezmie
# go przy nastepnym wdrozeniu (3-wdroz-aplikacje.ps1). Zeby funkcje wylaczyc,
# usun sekret: aws secretsmanager delete-secret --secret-id notarai/apify
# i wdroz ponownie.
param(
    [string]$Profil = "notarai-admin",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971"
)
$ErrorActionPreference = "Stop"
$Nazwa = "notarai/apify"

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

$token = Wczytaj-Ukryty "Wklej token Apify (apify_api_..., nie bedzie widoczny)"
if ($token -notmatch '^apify_api_[A-Za-z0-9]{20,}$') {
    throw "To nie wyglada na token Apify (powinien zaczynac sie od apify_api_). Nic nie zapisalem."
}

$plik = Join-Path $env:TEMP ("notarai-apify-" + [guid]::NewGuid().ToString("N") + ".json")
try {
    # Plik tylko dla biezacego uzytkownika, bez BOM (aws czyta go jako tekst).
    New-Item -ItemType File -Path $plik | Out-Null
    $acl = Get-Acl $plik
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        [Security.Principal.WindowsIdentity]::GetCurrent().Name, "FullControl", "Allow")))
    Set-Acl $plik $acl
    $json = @{ token = $token } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($plik, $json, (New-Object Text.UTF8Encoding($false)))
    $token = $null; $json = $null

    $wartosc = "file://" + $plik.Replace("\", "/")
    if (Czy-Aws secretsmanager describe-secret --secret-id $Nazwa) {
        & aws secretsmanager put-secret-value --secret-id $Nazwa --secret-string $wartosc `
            --profile $Profil --region $Region --query VersionId --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie podmienic sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Podmieniono token w sekrecie $Nazwa" -ForegroundColor Green
    } else {
        & aws secretsmanager create-secret --name $Nazwa `
            --description "notarai - token Apify (pobieranie ksiag wieczystych z EKW)" `
            --secret-string $wartosc --tags "Key=projekt,Value=notarai" `
            --profile $Profil --region $Region --query ARN --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie zalozyc sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Zalozono sekret $Nazwa w regionie $Region" -ForegroundColor Green
    }
} finally {
    if (Test-Path $plik) { Remove-Item $plik -Force }
}
Write-Host "Teraz wdroz aplikacje: infra\3-wdroz-aplikacje.ps1 (obraz bez zmian kodu nie wymaga przebudowy)"
