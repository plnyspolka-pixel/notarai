# notarai - wysyla zacommitowane zmiany do repozytorium kodu na GitHub
#
# Uruchom z dowolnego katalogu:
#   powershell -ExecutionPolicy Bypass -File C:\Users\Pieczak\notarai\infra\wyslij-kod.ps1
#
# Repozytorium: https://github.com/plnyspolka-pixel/notarai (zdalne "origin").
# Historia zostala przeniesiona z AWS CodeCommit 07.11.2026 - CodeCommit jest
# zamkniety dla nowych klientow i nie dostaje nowych funkcji. Pomocnik
# git-remote-codecommit nie jest juz potrzebny; git loguje sie do GitHub
# przez Git Credential Manager (przy pierwszym wypchnieciu otworzy przegladarke).
param(
    [string]$Galaz = "master",
    [string]$Zdalne = "https://github.com/plnyspolka-pixel/notarai.git"
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot

function Uruchom-Git {
    # git pisze postep wysylki na stderr. Windows PowerShell 5.1 przy
    # ErrorActionPreference=Stop robi z tego blad krytyczny i przerywa skrypt,
    # chociaz git zwrocil zero. O powodzeniu decyduje kod wyjscia, nie stderr.
    $poprzednie = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & git @args } finally { $ErrorActionPreference = $poprzednie }
}

# Stare klony maja "origin" wskazujacy na CodeCommit - przepinamy na GitHub.
$obecne = (Uruchom-Git -C $korzen remote get-url origin 2>$null)
if ($LASTEXITCODE -ne 0) {
    Uruchom-Git -C $korzen remote add origin $Zdalne
} elseif ("$obecne".Trim() -ne $Zdalne) {
    Write-Host "Zdalne origin wskazywalo na $("$obecne".Trim()) - przepinam na GitHub." -ForegroundColor Yellow
    Uruchom-Git -C $korzen remote set-url origin $Zdalne
}

$brudne = Uruchom-Git -C $korzen status --porcelain
if ($brudne) {
    Write-Host "Uwaga: sa niezacommitowane zmiany - zostana na dysku, wysylam tylko commity." -ForegroundColor Yellow
}

Write-Host "== Wysylam galaz $Galaz do GitHub" -ForegroundColor Cyan
Uruchom-Git -C $korzen push -u origin $Galaz
if ($LASTEXITCODE -ne 0) { throw "Wyslanie nie powiodlo sie (kod $LASTEXITCODE)." }

$lokalny = (Uruchom-Git -C $korzen rev-parse $Galaz).Trim()
$zdalny = (Uruchom-Git -C $korzen rev-parse "origin/$Galaz").Trim()
if ($lokalny -ne $zdalny) { throw "Po wyslaniu wersje sie roznia: lokalnie $lokalny, na GitHub $zdalny." }

Write-Host ""
Write-Host "== Gotowe. GitHub ma ten sam commit: $($lokalny.Substring(0,12))" -ForegroundColor Green
