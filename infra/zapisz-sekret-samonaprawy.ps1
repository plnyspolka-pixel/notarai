# notarai - token GitHub samonaprawy (sekret notarai/samonaprawa-github)
#
# Uruchom (z dowolnego katalogu):
#   powershell -ExecutionPolicy Bypass -File <katalog repo>\infra\zapisz-sekret-samonaprawy.ps1
#
# Najpierw utworz token na GitHubie (konto wlasciciela repozytorium):
#   https://github.com/settings/personal-access-tokens/new
#   - Token name: notarai-samonaprawa, Expiration: 1 rok (przypomnienie w kalendarzu)
#   - Repository access: Only select repositories -> plnyspolka-pixel/notarai
#   - Permissions (Repository): Contents: Read and write, Pull requests: Read and write,
#     Issues: Read and write, Actions: Read and write (Metadata: Read - automatycznie)
#   - Generate token -> skopiuj (Ctrl+C)
#
# Skrypt pyta o token (nie widac go na ekranie), zapisuje w Secrets Manager.
# Nie trafia do historii PowerShella ani do argumentow aws. Dalej wszystko samo:
#   - aplikacja dostaje token przy nastepnym wdrozeniu (wdrozenie.yml sam go wykrywa)
#     i zglasza nowe bledy w czasie rzeczywistym,
#   - workflow samonaprawy scala poprawki tym tokenem, wiec uruchamiaja sie zwykle
#     testy i wdrozenie.
# Bez tokenu samonaprawa i tak dziala - przeglad bledow co 30 minut.
# Rotacja: uruchom skrypt ponownie z nowym tokenem.
param(
    [string]$Profil = "notarai-admin",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971"
)
$ErrorActionPreference = "Stop"
$Nazwa = "notarai/samonaprawa-github"

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

$bezpieczny = Read-Host "Wklej token GitHub (github_pat_...)" -AsSecureString
$token = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($bezpieczny))
if ($token -notmatch '^(github_pat_|ghp_)[A-Za-z0-9_]{20,}$') {
    $token = $null
    throw "To nie wyglada na token GitHub (github_pat_... albo ghp_...)."
}

$plik = Join-Path $env:TEMP ("notarai-sn-" + [guid]::NewGuid().ToString("N") + ".json")
try {
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
            --description "notarai - token GitHub samonaprawy (zgloszenia bledow, poprawki)" `
            --secret-string $wartosc --tags "Key=projekt,Value=notarai" `
            --profile $Profil --region $Region --query ARN --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie zalozyc sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Zalozono sekret $Nazwa w regionie $Region" -ForegroundColor Green
    }
} finally {
    if (Test-Path $plik) { Remove-Item $plik -Force }
}
Write-Host ""
Write-Host "Gotowe. Aplikacja dostanie token przy najblizszym wdrozeniu (samo, po kolejnej zmianie na master)." -ForegroundColor Cyan
Write-Host "Zeby od razu: GitHub -> Actions -> 'NotarAI - wdrozenie na app.notarai.pl' -> Run workflow."
