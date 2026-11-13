@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set REGION=eu-central-1
set AWS_REGION=eu-central-1
set STOS=notarai-claude-iam
set UZYTKOWNIK=notarai-claude
set PROFIL_ADMIN=%~1
if "%PROFIL_ADMIN%"=="" set PROFIL_ADMIN=notarai-admin

echo ==========================================================
echo  notarai - staly dostep Claude do AWS bez logowania
echo ==========================================================
echo  Co sie stanie:
echo   1. jednorazowo logujesz sie profilem %PROFIL_ADMIN% (aws login,
echo      otworzy sie przegladarka) - jesli sesja juz jest, nic nie robi
echo   2. CloudFormation zaklada uzytkownika IAM %UZYTKOWNIK%
echo      (szablon notarai-claude-iam.yaml: pelna obsluga infrastruktury
echo      projektu, BEZ dostepu do plikow spraw kancelarii)
echo   3. powstaje staly klucz dostepu; trafia do ~\.aws\credentials jako
echo      profil %UZYTKOWNIK% ORAZ jako profil default (skrypty infra\*.ps1
echo      bez -Profil przestaja wymagac aws login)
echo   4. sekret klucza laduje w schowku Windows - wklejasz go w claude.ai
echo      do zmiennej srodowiska NOTARAI_AWS_SECRET_ACCESS_KEY (instrukcja
echo      na koncu); nigdzie indziej go nie zapisuj
echo.

echo [1/5] Sesja administratora (profil %PROFIL_ADMIN%)...
aws sts get-caller-identity --profile %PROFIL_ADMIN% >nul 2>&1
if errorlevel 1 (
  echo       Otwieram logowanie - zaloguj sie w przegladarce i wroc tutaj.
  aws login --profile %PROFIL_ADMIN%
)
for /f "delims=" %%a in ('aws sts get-caller-identity --profile %PROFIL_ADMIN% --query Arn --output text 2^>nul') do set ARN=%%a
if not defined ARN goto blad
echo       zalogowano jako: %ARN%
echo.

echo [2/5] CloudFormation: stos %STOS%...
aws cloudformation deploy --profile %PROFIL_ADMIN% --region %REGION% --stack-name %STOS% --template-file notarai-claude-iam.yaml --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset --tags projekt=notarai
if errorlevel 1 goto blad
echo.

echo [3/5] Klucz dostepu dla %UZYTKOWNIK%...
for /f "tokens=1,2" %%a in ('aws iam create-access-key --profile %PROFIL_ADMIN% --user-name %UZYTKOWNIK% --query "AccessKey.[AccessKeyId,SecretAccessKey]" --output text') do (
  set KID=%%a
  set KSEC=%%b
)
if not defined KSEC (
  echo       BLAD: nie udalo sie utworzyc klucza. Jesli komunikat wyzej mowi o limicie
  echo       ^(LimitExceeded^), uzytkownik ma juz 2 klucze - usun stary:
  echo       aws iam list-access-keys --user-name %UZYTKOWNIK% --profile %PROFIL_ADMIN%
  echo       aws iam delete-access-key --user-name %UZYTKOWNIK% --access-key-id ^<stary^> --profile %PROFIL_ADMIN%
  goto blad
)
echo       utworzono klucz %KID%
echo.

echo [4/5] Zapis w profilach %UZYTKOWNIK% i default...
for %%p in (%UZYTKOWNIK% default) do (
  aws configure set aws_access_key_id %KID% --profile %%p
  aws configure set aws_secret_access_key %KSEC% --profile %%p
  aws configure set region %REGION% --profile %%p
)
python usun_login_session.py
<nul set /p="%KSEC%" | clip
set KSEC=
echo       sekret klucza jest w schowku (Ctrl+V), na ekranie go nie pokazuje.
echo.

echo [5/5] Sprawdzenie nowej tozsamosci...
aws sts get-caller-identity --profile %UZYTKOWNIK% --query Arn --output text
if errorlevel 1 goto blad
echo.
echo ==========================================================
echo  GOTOWE. Teraz Claude w chmurze (claude.ai/code):
echo ==========================================================
echo  1. claude.ai -^> Code -^> Settings -^> Environments -^> srodowisko,
echo     w ktorym pracujesz nad notarai (np. "notarai" albo "Default")
echo     -^> Edit -^> Environment variables. Dodaj DWIE zmienne:
echo        NOTARAI_AWS_ACCESS_KEY_ID      = %KID%
echo        NOTARAI_AWS_SECRET_ACCESS_KEY  = (Ctrl+V - sekret ze schowka)
echo     Zapisz. Nowe sesje w tym srodowisku dostana klucz; Claude na
echo     starcie uruchamia: source infra/aws-z-env.sh (opis w CLAUDE.md).
echo  2. Po wklejeniu skopiuj do schowka cokolwiek innego, zeby sekret
echo     nie zostal w schowku.
echo  3. Claude Code na tym komputerze: profil default juz ma klucz,
echo     skrypty infra\*.ps1 dzialaja bez aws login. Skrypty z parametrem
echo     -Profil notarai-admin uruchamiaj z -Profil %UZYTKOWNIK%.
echo.
echo  Bezpieczenstwo: klucz nie wygasa. Gdy wycieknie - w konsoli IAM
echo  (uzytkownik %UZYTKOWNIK%, Security credentials) dezaktywuj go
echo  i uruchom ten skrypt ponownie. Rotacja: raz na kilka miesiecy.
goto koniec

:blad
echo.
echo BLAD - przerwano. Przeczytaj komunikat wyzej.
set KSEC=

:koniec
echo.
pause
