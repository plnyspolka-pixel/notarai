@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set REGION=eu-central-1
set AWS_REGION=eu-central-1
set STOS=pieczapp-iam
set UZYTKOWNIK=pieczapp-claude

echo ==========================================================
echo  pieczapp - staly dostep do AWS bez codziennego logowania
echo ==========================================================
echo  Co sie stanie:
echo   1. logujesz sie rootem OSTATNI raz (otworzy sie przegladarka)
echo   2. CloudFormation zaklada uzytkownika IAM %UZYTKOWNIK%
echo      z uprawnieniami tylko do Bedrock w UE
echo   3. powstaje klucz dostepu i trafia prosto do ~/.aws/credentials
echo      (nie jest wyswietlany)
echo   4. profil default przestaje uzywac sesji root
echo.

echo [1/5] Sesja root...
aws sts get-caller-identity --profile default >nul 2>&1
if errorlevel 1 (
  echo       Otwieram logowanie - zaloguj sie w przegladarce i wroc tutaj.
  aws login --profile default
)
for /f "delims=" %%a in ('aws sts get-caller-identity --profile default --query Arn --output text 2^>nul') do set ARN=%%a
if not defined ARN goto blad
echo       zalogowano jako: %ARN%
echo.

echo [2/5] CloudFormation: stos %STOS%...
aws cloudformation deploy --profile default --region %REGION% --stack-name %STOS% --template-file pieczapp-iam.yaml --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset
if errorlevel 1 goto blad
echo.

echo [3/5] Klucz dostepu dla %UZYTKOWNIK%...
for /f "tokens=1,2" %%a in ('aws iam create-access-key --profile default --user-name %UZYTKOWNIK% --query "AccessKey.[AccessKeyId,SecretAccessKey]" --output text') do (
  set KID=%%a
  set KSEC=%%b
)
if not defined KSEC (
  echo       BLAD: nie udalo sie utworzyc klucza. Jesli komunikat wyzej mowi o limicie
  echo       ^(LimitExceeded^), uzytkownik ma juz 2 klucze - usun stary w konsoli IAM.
  goto blad
)
echo       utworzono klucz %KID%
echo.

echo [4/5] Zapis w profilu default...
aws configure set aws_access_key_id %KID% --profile default
aws configure set aws_secret_access_key %KSEC% --profile default
aws configure set region %REGION% --profile default
set KSEC=
python usun_login_session.py
echo.

echo [5/5] Sprawdzenie nowej tozsamosci i dostepu do Bedrock...
aws sts get-caller-identity --profile default --query Arn --output text
aws bedrock list-inference-profiles --profile default --region %REGION% --query "inferenceProfileSummaries[?starts_with(inferenceProfileId,'eu.anthropic')].inferenceProfileId" --output text
if errorlevel 1 goto blad
echo.
echo GOTOWE. Od teraz AWS CLI, Claude Code i pieczapp dzialaja bez logowania.
echo Root sluzy juz tylko do konsoli AWS w przegladarce.
goto koniec

:blad
echo.
echo Zatrzymano na bledzie - przeczytaj komunikat wyzej.

:koniec
echo.
pause
