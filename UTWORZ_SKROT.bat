@echo off
REM Tworzy na Pulpicie skrot "pieczapp" do uruchom.bat z sygnetem NotarAI.
set APP=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\NotarAI.lnk');" ^
  "$s.TargetPath='%APP%uruchom.bat';" ^
  "$s.WorkingDirectory='%APP%';" ^
  "$s.IconLocation='%APP%static\notarai.ico,0';" ^
  "$s.Description='NotarAI - asystent kancelarii';" ^
  "$s.Save(); Write-Host 'Skrot NotarAI utworzony na Pulpicie.'"
pause
