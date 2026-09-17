@echo off
REM Tworzy na Pulpicie skrot "pieczapp" do uruchom.bat z ikona osiolka.
set APP=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\pieczapp.lnk');" ^
  "$s.TargetPath='%APP%uruchom.bat';" ^
  "$s.WorkingDirectory='%APP%';" ^
  "$s.IconLocation='%APP%static\pieczapp.ico,0';" ^
  "$s.Description='pieczapp - asystent kancelarii';" ^
  "$s.Save(); Write-Host 'Skrot pieczapp utworzony na Pulpicie.'"
pause
