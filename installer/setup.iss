[Setup]
AppName=MMMUT WiFi Auto Login
AppVersion=2.1.0
AppPublisher=Nitin
DefaultDirName={autopf}\MMMUT WiFi Auto Login
DefaultGroupName=MMMUT WiFi Auto Login
OutputDir=.
OutputBaseFilename=MMMUT_WiFi_Auto_Login_Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=..\assets\icon.ico
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\MMMUT WiFi Auto Login.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\MMMUT WiFi Auto Login"; Filename: "{app}\MMMUT WiFi Auto Login.exe"
Name: "{autodesktop}\MMMUT WiFi Auto Login"; Filename: "{app}\MMMUT WiFi Auto Login.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MMMUT WiFi Auto Login.exe"; Description: "{cm:LaunchProgram,MMMUT WiFi Auto Login}"; Flags: nowait postinstall skipifsilent
