@echo off
REM Uruchamia testy pytest dla pieczapp

cd /d "%~dp0"

REM Sprawdz czy istnieje srodowisko wirtualne
if not exist .venv (
  echo Brak srodowiska wirtualnego. Uruchamiam uruchom.bat...
  echo Nacisnij Ctrl+C po uruchomieniu serwera, aby kontynuowac.
  call uruchom.bat
  exit /b
)

REM Aktywuj srodowisko
call .venv\Scripts\activate.bat

REM Sprawdz czy pytest jest zainstalowany
python -c "import pytest" 2>nul
if errorlevel 1 (
  echo Instaluje pytest...
  pip install -q pytest pytest-mock
)

REM Uruchom testy
echo.
echo ========================================
echo Uruchamiam testy pytest...
echo ========================================
echo.

python -m pytest %*

if errorlevel 1 (
  echo.
  echo Testy NIEUDANE
  exit /b 1
) else (
  echo.
  echo Wszystkie testy UDANE
  exit /b 0
)
