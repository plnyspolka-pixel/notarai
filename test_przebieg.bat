@echo off
chcp 65001 >nul
cd /d "%~dp0"
set FOLDER=C:\Users\Pieczak\Desktop\trening PieczAppa
set AWS_REGION=eu-central-1

echo ============================================
echo  pieczapp - przebieg testowy: %FOLDER%
echo ============================================
echo.

if not exist .venv (
  echo [0/4] Pierwsze uruchomienie - tworze srodowisko, to potrwa kilka minut...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

echo [1/4] Sprawdzam sesje AWS...
aws sts get-caller-identity --profile pieczapp >nul 2>&1
if errorlevel 1 (
  echo       Sesja wygasla. Otworzy sie przegladarka - ZALOGUJ SIE, potem wroc tutaj.
  aws login --profile pieczapp
  if errorlevel 1 aws sso login --profile pieczapp
  aws sts get-caller-identity --profile pieczapp >nul 2>&1
  if errorlevel 1 (
    echo       BLAD: nadal brak sesji AWS. Zatrzymuje sie.
    goto koniec
  )
)
echo       OK, AWS dziala.
echo.

echo [2/4] Testy automatyczne (najpierw brakujace biblioteki)...
pip install -q -r requirements.txt
python -m pytest -q --color=no -p no:cacheprovider
if errorlevel 1 (
  echo       BLAD: testy nie przeszly. Zatrzymuje sie.
  goto koniec
)
echo.

echo [3/4] Pelny przebieg na plikach z folderu (2 wywolania modelu, 1-3 minuty)...
python przebieg_testowy.py "%FOLDER%"
echo.

echo [4/4] Koniec. Wyniki: "%FOLDER%\wynik_pieczapp"
:koniec
echo.
echo Mozesz zamknac to okno.
pause
