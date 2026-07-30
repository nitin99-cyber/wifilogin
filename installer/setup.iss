; Inno Setup Script for MMMUT WiFi Auto Login
; Publisher: Nitin Deep

#define MyAppName "MMMUT WiFi Auto Login"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Nitin Deep"
#define MyAppExeName "MMMUT WiFi Auto Login.exe"
#define MyAppAppId "com.nitin.mmmut.wifi"

[Setup]
; AppId uniquely identifies this application. Do not change this in future releases for seamless upgrades.
AppId={#MyAppAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

; Default installation directory in Program Files
DefaultDirName={autopf}\{#MyAppName}

; Start Menu folder name
DefaultGroupName={#MyAppName}

; Output configuration (Generates the installer in the root folder)
OutputDir=..\
OutputBaseFilename=MMMUT-WiFi-Auto-Login-Setup

; Icons and styling
SetupIconFile=..\assets\icon.ico
AllowNoIcons=yes
WizardStyle=modern

; Compression settings for a smaller installer
Compression=lzma
SolidCompression=yes

; Dynamically include License and Readme if they exist in the parent directory
#ifexist "..\LICENSE.txt"
LicenseFile=..\LICENSE.txt
#endif
#ifexist "..\README.txt"
InfoBeforeFile=..\README.txt
#endif

[Tasks]
; Desktop shortcut task, checked by default
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copy the standalone executable to the installation directory
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu - Application Shortcut
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
; Start Menu - Uninstall Shortcut
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Desktop Shortcut (if user checked the task)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExeName}"

[Registry]
; Add to Windows startup via HKCU Run key (no admin required, shows in Task Manager)
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueName: "{#MyAppName}"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" --background"; Flags: uninsdeletevalue

[Run]
; Option to launch the application GUI immediately after finishing installation (Checked by default)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Clean up any legacy scheduled task from older versions
Filename: "schtasks"; Parameters: "/Delete /TN ""MMMUT WiFi Auto Login"" /F"; Flags: runhidden nowait; Check: IsWin64

[UninstallDelete]
; Ensures the installation folder is removed during uninstall
Type: filesandordirs; Name: "{app}"
