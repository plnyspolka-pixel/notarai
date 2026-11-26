[Setup]
AppId={{48ABAE34-C8E3-4337-87C1-22E39BBDA5DE}
AppName=NotarAI V2 Preview
AppVersion=2.0.0
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

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NotarAI V2 Preview"; Filename: "{app}\runtime\python.exe"; Parameters: "-X utf8 ""{app}\launch.py"""; WorkingDir: "{app}"

[Run]
Filename: "{app}\runtime\python.exe"; Parameters: "-X utf8 ""{app}\launch.py"""; WorkingDir: "{app}"; Description: "Uruchom NotarAI V2 Preview"; Flags: nowait postinstall skipifsilent
