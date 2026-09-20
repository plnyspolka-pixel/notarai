# notarai - wysyla zacommitowane zmiany do repozytorium w AWS (CodeCommit)
#
# Uruchom z dowolnego katalogu:
#   powershell -ExecutionPolicy Bypass -File C:\Users\Pieczak\notarai\infra\wyslij-kod.ps1
#
# Po co osobny skrypt: git rozmawia z CodeCommit przez pomocnika
# git-remote-codecommit, ktory siedzi w srodowisku wirtualnym projektu.
# Bez niego w sciezce zwykle "git push" konczy sie bledem
# "remote helper 'codecommit' aborted session".
param(
    [string]$Galaz = "master"
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot

# Pomocnik moze byc w srodowisku projektu albo w srodowisku pieczapp.
$kandydaci = @(
    (Join-Path $korzen ".venv\Scripts"),
    "C:\Users\Pieczak\pieczapp\.venv\Scripts"
)
$sciezka = $kandydaci | Where-Object { Test-Path (Join-Path $_ "git-remote-codecommit.exe") } | Select-Object -First 1
if (-not $sciezka) {
    throw "Brak pomocnika git-remote-codecommit. Zainstaluj go w srodowisku projektu:`n  .venv\Scripts\python.exe -m pip install git-remote-codecommit"
}
$env:PATH = "$sciezka;$env:PATH"

function Uruchom-Git {
    # git pisze postep wysylki na stderr. Windows PowerShell 5.1 przy
    # ErrorActionPreference=Stop robi z tego blad krytyczny i przerywa skrypt,
    # chociaz git zwrocil zero. O powodzeniu decyduje kod wyjscia, nie stderr.
    $poprzednie = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & git @args } finally { $ErrorActionPreference = $poprzednie }
}

$brudne = Uruchom-Git -C $korzen status --porcelain
if ($brudne) {
    Write-Host "Uwaga: sa niezacommitowane zmiany - zostana na dysku, wysylam tylko commity." -ForegroundColor Yellow
}

Write-Host "== Wysylam galaz $Galaz do AWS" -ForegroundColor Cyan
Uruchom-Git -C $korzen push origin $Galaz
if ($LASTEXITCODE -ne 0) { throw "Wyslanie nie powiodlo sie (kod $LASTEXITCODE)." }

$lokalny = (Uruchom-Git -C $korzen rev-parse $Galaz).Trim()
$zdalny = (Uruchom-Git -C $korzen rev-parse "origin/$Galaz").Trim()
if ($lokalny -ne $zdalny) { throw "Po wyslaniu wersje sie roznia: lokalnie $lokalny, w AWS $zdalny." }

Write-Host ""
Write-Host "== Gotowe. AWS ma ten sam commit: $($lokalny.Substring(0,12))" -ForegroundColor Green
