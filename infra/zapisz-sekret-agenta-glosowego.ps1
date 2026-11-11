# notarai - token webhookow agenta glosowego ElevenLabs (sekret notarai/agent-glosowy)
#
# Uruchom (z dowolnego katalogu):
#   powershell -ExecutionPolicy Bypass -File <katalog repo>\infra\zapisz-sekret-agenta-glosowego.ps1
#
# Skrypt sam losuje token (48 znakow), zapisuje go w Secrets Manager i kopiuje
# do schowka. Ten sam token wklejasz w ElevenLabs: Agents -> Secrets ->
# "notarai_agent_glosowy_token" -> Edit (narzedzia agenta wysylaja go
# w naglowku X-Notarai-Agent). Potem wdrazasz aplikacje: infra\3-wdroz-aplikacje.ps1
# - od tej chwili /api/agent-glosowy przyjmuje tylko zapytania z tym tokenem.
# Kolejnosc ma znaczenie tylko na kilka minut: najpierw ElevenLabs, potem wdrozenie.
#
# Token nie trafia na ekran, do historii PowerShella ani do argumentow aws.
# Ponowne uruchomienie = nowy token (rotacja): powtorz wklejenie w ElevenLabs.
# Wylaczenie wymogu tokenu: aws secretsmanager delete-secret --secret-id notarai/agent-glosowy
# i wdrozenie.
param(
    [string]$Profil = "notarai-admin",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971"
)
$ErrorActionPreference = "Stop"
$Nazwa = "notarai/agent-glosowy"

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

$znaki = [char[]]"ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
$bajty = New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bajty)
$token = -join ($bajty | ForEach-Object { $znaki[$_ % $znaki.Length] })

$plik = Join-Path $env:TEMP ("notarai-agent-" + [guid]::NewGuid().ToString("N") + ".json")
try {
    New-Item -ItemType File -Path $plik | Out-Null
    $acl = Get-Acl $plik
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        [Security.Principal.WindowsIdentity]::GetCurrent().Name, "FullControl", "Allow")))
    Set-Acl $plik $acl
    $json = @{ token = $token } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($plik, $json, (New-Object Text.UTF8Encoding($false)))
    Set-Clipboard -Value $token
    $token = $null; $json = $null

    $wartosc = "file://" + $plik.Replace("\", "/")
    if (Czy-Aws secretsmanager describe-secret --secret-id $Nazwa) {
        & aws secretsmanager put-secret-value --secret-id $Nazwa --secret-string $wartosc `
            --profile $Profil --region $Region --query VersionId --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie podmienic sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Podmieniono token w sekrecie $Nazwa" -ForegroundColor Green
    } else {
        & aws secretsmanager create-secret --name $Nazwa `
            --description "notarai - token webhookow agenta glosowego ElevenLabs" `
            --secret-string $wartosc --tags "Key=projekt,Value=notarai" `
            --profile $Profil --region $Region --query ARN --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie zalozyc sekretu (kod $LASTEXITCODE)." }
        Write-Host "== Zalozono sekret $Nazwa w regionie $Region" -ForegroundColor Green
    }
} finally {
    if (Test-Path $plik) { Remove-Item $plik -Force }
}
Write-Host ""
Write-Host "Token jest w schowku. Teraz:" -ForegroundColor Cyan
Write-Host "  1. ElevenLabs -> Agents -> Secrets -> notarai_agent_glosowy_token -> Edit -> wklej (Ctrl+V) -> Save"
Write-Host "  2. Wdroz aplikacje: powershell -ExecutionPolicy Bypass -File infra\3-wdroz-aplikacje.ps1"
Write-Host "  3. Wyczysc schowek (skopiuj cokolwiek innego)."
