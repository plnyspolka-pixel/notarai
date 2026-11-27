[Setup]
AppId={{48ABAE34-C8E3-4337-87C1-22E39BBDA5DE}
AppName=NotarAI V2 Preview
AppVersion=2.4.1
DefaultDirName={localappdata}\Programs\NotarAI V2 Preview
DefaultGroupName=NotarAI V2 Preview
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputBaseFilename=NotarAI-V2-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; An update closes the running worker (its files are in use) and does not restart it by itself.
CloseApplications=force
RestartApplications=no

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Ikona NotarAI na pulpicie"; Flags: checkedonce

[Icons]
Name: "{group}\NotarAI"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-X utf8 ""{app}\launch.py"""; WorkingDir: "{app}"
Name: "{userdesktop}\NotarAI"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-X utf8 ""{app}\launch.py"""; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\NotarAI w tle"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-X utf8 ""{app}\launch.py"" --serve"; WorkingDir: "{app}"

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: "-X utf8 ""{app}\launch.py"""; WorkingDir: "{app}"; Description: "Uruchom NotarAI"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Get-Process pythonw,python -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{app}\*' } | Stop-Process -Force"""; Flags: runhidden; RunOnceId: "StopNotarAI"
