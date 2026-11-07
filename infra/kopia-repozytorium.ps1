# notarai - kopia zapasowa repozytorium kodu poza AWS, na tym komputerze
#
#   powershell -ExecutionPolicy Bypass -File C:\Users\Pieczak\notarai\infra\kopia-repozytorium.ps1
#
# Glowne repozytorium to GitHub (https://github.com/plnyspolka-pixel/notarai,
# od 07.11.2026; wczesniej AWS CodeCommit). Historia nie moze zyc tylko u
# jednego dostawcy, wiec skrypt robi dwie rzeczy:
#   1. lustro (bare) C:\Users\Pieczak\kopie-repozytoriow\notarai.git - z niego
#      mozna sklonowac albo wypchnac historie gdziekolwiek indziej,
#   2. jeden plik notarai-RRRR-MM-DD.bundle z cala historia - do skopiowania na
#      dysk zewnetrzny; odtworzenie: git clone notarai-RRRR-MM-DD.bundle notarai
# Trzyma 10 ostatnich plikow .bundle. Kod nie zawiera danych kancelarii ani
# sekretow (Zalacznik nr 2 do umowy powierzenia, lit. H).
param(
    [string]$Cel = "C:\Users\Pieczak\kopie-repozytoriow"
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot

function Uruchom-Git {
    # git pisze postep na stderr; o powodzeniu decyduje kod wyjscia.
    $poprzednie = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & git @args 2>&1 | ForEach-Object { "$_" }
    $kod = $LASTEXITCODE
    $ErrorActionPreference = $poprzednie
    if ($kod -ne 0) { throw "git $($args -join ' ') zakonczyl sie kodem $kod" }
}

New-Item -ItemType Directory -Force $Cel | Out-Null
$lustro = Join-Path $Cel "notarai.git"

Write-Host "== Lustro: $lustro"
if (-not (Test-Path $lustro)) {
    Uruchom-Git clone --mirror "$korzen" "$lustro"
} else {
    Uruchom-Git -C "$lustro" remote set-url origin "$korzen"
    Uruchom-Git -C "$lustro" fetch --prune origin
}

$plik = Join-Path $Cel ("notarai-" + (Get-Date -Format "yyyy-MM-dd") + ".bundle")
Write-Host "== Plik: $plik"
Uruchom-Git -C "$korzen" bundle create "$plik" --all
Uruchom-Git bundle verify "$plik"

Get-ChildItem $Cel -Filter "notarai-*.bundle" | Sort-Object Name -Descending |
    Select-Object -Skip 10 | Remove-Item -Confirm:$false

$lokalny = (& git -C "$korzen" rev-parse HEAD).Trim()
$wKopii = (& git -C "$lustro" rev-parse HEAD).Trim()
if ($lokalny -ne $wKopii) { throw "Lustro ma $wKopii, a repozytorium $lokalny" }
Write-Host ""
Write-Host "== Gotowe. Kopia ma ten sam commit: $($lokalny.Substring(0, 12))"
