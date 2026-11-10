# Backend notarai dla aplikacji klienta na stanowisku deweloperskim:
# tryb lokalny, SMS w trybie testowym (nic nie wychodzi, kod wraca w odpowiedzi),
# kancelarie demo z terminarzem, CORS dla Expo web (localhost:8081).
# Uruchom z katalogu repozytorium: powershell -ExecutionPolicy Bypass -File scripts\dev-klient-backend.ps1
# Telefon z Expo Go w tej samej sieci: dodaj -Adres 0.0.0.0 (i port 8000 w zaporze, tylko zaufana siec).
param([string]$Adres = "127.0.0.1")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:PIECZAPP_SMS_TRYB = "test"
$env:PIECZAPP_PRZYPOMNIENIA = "0"
$env:PIECZAPP_KALKULATOR_ORIGINS = "https://notarai.pl,https://www.notarai.pl,http://localhost:8081,http://127.0.0.1:8081"
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python scripts\demo_klienta.py
& $python -m uvicorn app:app --host $Adres --port 8000
