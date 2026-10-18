# notarai - budowa pomocnika notariusza jako jednego pliku .exe
#
# Uruchom z katalogu notarai:
#   powershell -ExecutionPolicy Bypass -File infra\zbuduj-pomocnika.ps1
#
# Wynik: static\pobierz\notarai-pomocnik.exe - aplikacja serwuje go jako plik
# do pobrania w kreatorze instalacji. Obraz kontenera powstaje z commita
# (git archive), wiec po zbudowaniu .exe trzeba go zacommitowac, a potem
# zbudowac i wdrozyc obraz jak zwykle (2-zbuduj-obraz, 3-wdroz-aplikacje).
#
# Narzedzia budowania (PyInstaller) leza w osobnym srodowisku .venv-pomocnik,
# zeby nie mieszac ich z zaleznosciami aplikacji. Pomocnik korzysta tylko z
# biblioteki standardowej Pythona, wiec plik jest maly.
param(
    [string]$Python = ""
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $korzen ".venv-pomocnik"
$py = Join-Path $venv "Scripts\python.exe"
$cel = Join-Path $korzen "static\pobierz"
$robocze = Join-Path $korzen "build\pomocnik"

function Sprawdz($opis) {
    if ($LASTEXITCODE -ne 0) { throw "$opis nie powiodlo sie (kod $LASTEXITCODE)." }
}

if (-not (Test-Path $py)) {
    Write-Host "== Tworze srodowisko budowania $venv" -ForegroundColor Cyan
    if ($Python) { & $Python -m venv $venv }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv $venv }
    else { & python -m venv $venv }
    Sprawdz "Tworzenie srodowiska"
}

Write-Host "== Instaluje PyInstaller" -ForegroundColor Cyan
& $py -m pip install --quiet --disable-pip-version-check "pyinstaller>=6.16,<7" "pillow>=11"
Sprawdz "Instalacja PyInstallera"

$wersja = (& $py -c "import sys; sys.path.insert(0, r'$korzen'); from pomocnik.klient import WERSJA; print(WERSJA)").Trim()
Sprawdz "Odczyt wersji"
Write-Host "== Buduje pomocnika $wersja" -ForegroundColor Cyan

Push-Location $korzen
try {
    & $py -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name notarai-pomocnik `
        --icon (Join-Path $korzen "static\logo.png") `
        --add-data ((Join-Path $korzen "static\favicon.png") + ";static") `
        --paths $korzen `
        --distpath $cel `
        --workpath $robocze `
        --specpath $robocze `
        --log-level WARN `
        (Join-Path $korzen "pomocnik\__main__.py")
    Sprawdz "PyInstaller"
} finally {
    Pop-Location
}

$plik = Join-Path $cel "notarai-pomocnik.exe"
$rozmiar = [math]::Round((Get-Item $plik).Length / 1MB, 1)
$skrot = (Get-FileHash $plik -Algorithm SHA256).Hash.ToLower()
Set-Content -Path (Join-Path $cel "notarai-pomocnik.json") -Encoding ASCII -Value (
    '{"wersja": "' + $wersja + '", "sha256": "' + $skrot + '"}')

Write-Host ""
Write-Host "Gotowe: $plik ($rozmiar MB)" -ForegroundColor Green
Write-Host "SHA-256: $skrot"
Write-Host "Dalej: zacommituj static\pobierz, potem infra\2-zbuduj-obraz.ps1 i infra\3-wdroz-aplikacje.ps1"
