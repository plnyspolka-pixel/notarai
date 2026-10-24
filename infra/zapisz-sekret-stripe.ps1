# notarai - zapisuje klucze Stripe w Secrets Manager (sekret notarai/stripe)
#
# Uruchom (z dowolnego katalogu):
#   powershell -ExecutionPolicy Bypass -File C:\Users\Pieczak\notarai\infra\zapisz-sekret-stripe.ps1
#
# Skrypt pyta o dwa klucze z panelu Stripe:
#   1. klucz tajny API     Developers -> API keys -> Secret key (sk_live_...)
#                          albo klucz ograniczony (rk_live_...)
#   2. klucz webhooka      Developers -> Webhooks -> notarai-aplikacja ->
#                          Signing secret (whsec_...)
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
$Nazwa = "notarai/stripe"

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

$klucz = Wczytaj-Ukryty "Wklej klucz tajny Stripe (sk_live_... albo rk_live_..., nie bedzie widoczny)"
if ($klucz -notmatch '^(sk|rk)_(live|test)_[A-Za-z0-9]+$') {
    throw "To nie wyglada na klucz tajny Stripe (powinien zaczynac sie od sk_live_ albo rk_live_). Nic nie zapisalem."
}
if ($klucz -match '_test_') { Write-Host "Uwaga: to klucz TESTOWY - platnosci nie beda prawdziwe." -ForegroundColor Yellow }
$webhook = Wczytaj-Ukryty "Wklej klucz podpisu webhooka (whsec_..., nie bedzie widoczny)"
if ($webhook -notmatch '^whsec_[A-Za-z0-9]+$') {
    throw "To nie wyglada na klucz webhooka Stripe (powinien zaczynac sie od whsec_). Nic nie zapisalem."
}

$plik = Join-Path $env:TEMP ("notarai-stripe-" + [guid]::NewGuid().ToString("N") + ".json")
try {
    # Plik tylko dla biezacego uzytkownika, bez BOM (aws czyta go jako tekst).
    New-Item -ItemType File -Path $plik | Out-Null
    $acl = Get-Acl $plik
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        [Security.Principal.WindowsIdentity]::GetCurrent().Name, "FullControl", "Allow")))
    Set-Acl $plik $acl
    $json = @{ klucz = $klucz; webhook = $webhook } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($plik, $json, (New-Object Text.UTF8Encoding($false)))
    $klucz = $null; $webhook = $null; $json = $null

    $wartosc = "file://" + $plik.Replace("\", "/")
    if (Czy-Aws secretsmanager describe-secret --secret-id $Nazwa) {
        & aws secretsmanager put-secret-value --secret-id $Nazwa --secret-string $wartosc `
            --profile $Profil --region $Region --query VersionId --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie podmienic sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Podmieniono klucze w sekrecie $Nazwa" -ForegroundColor Green
    } else {
        & aws secretsmanager create-secret --name $Nazwa `
            --description "notarai - klucze Stripe (klucz API i podpis webhooka)" `
            --secret-string $wartosc --tags "Key=projekt,Value=notarai" `
            --profile $Profil --region $Region --query ARN --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie zalozyc sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Zalozono sekret $Nazwa w regionie $Region" -ForegroundColor Green
    }
} finally {
    if (Test-Path $plik) { Remove-Item $plik -Force }
}
Write-Host "Teraz wdroz aplikacje: infra\2-zbuduj-obraz.ps1, potem infra\3-wdroz-aplikacje.ps1"
