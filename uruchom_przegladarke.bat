@echo off
REM Przegladarka dla asysty formularzy. Osobny profil (nie miesza sie z Twoim
REM Chrome), port debugowania tylko na tym komputerze. Zaloguj sie w niej
REM certyfikatem do systemu urzedowego - pieczapp podlacza sie do JUZ
REM zalogowanej sesji i nigdy nie wpisuje hasla ani PIN-u.
set PROFIL=%LOCALAPPDATA%\pieczapp\przegladarka
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
  set PRZEGLADARKA="%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else (
  set PRZEGLADARKA="%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
)
start "" %PRZEGLADARKA% --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --user-data-dir="%PROFIL%" --no-first-run
