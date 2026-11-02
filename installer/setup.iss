; Inno Setup Script for MMMUT WiFi Auto Login
; Single source of truth for identity and version strings: metadata.py

#define MyAppName "MMMUT WiFi Auto Login"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "Nitin Deep"
#define MyAppURL "https://github.com/nitin99-cyber/mmmutwifilogin"
#define MyAppExeName "MMMUT WiFi Auto Login.exe"
#define MyAppId "com.nitin.mmmut.wifi"

[Setup]
; AppId uniquely identifies this application for seamless upgrades.
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation directories
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output configuration
OutputDir=.
OutputBaseFilename=MMMUT_WiFi_Auto_Login_Setup
SetupIconFile=..\assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

; Process and restart handling
CloseApplications=force
RestartApplications=False
ArchitecturesInstallIn64BitMode=x64compatible
UsedUserAreasWarning=no

; Version information metadata
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoTextVersion={#MyAppVersion}
VersionInfoCopyright=© 2026 {#MyAppPublisher}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Add to Windows startup via HKCU Run key (no admin required, shows in Task Manager)
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueName: "{#MyAppName}"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" --background"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Clean up any legacy scheduled task from older versions
Filename: "schtasks"; Parameters: "/Delete /TN ""{#MyAppName}"" /F"; Flags: runhidden nowait; RunOnceId: "DelLegacySchtasks"

[UninstallDelete]
; Ensures the installation folder is completely removed on uninstall
Type: filesandordirs; Name: "{app}"

[Code]
// Close running instance before installation starts
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    Exec('taskkill.exe', '/F /IM "{#MyAppExeName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(500);
  end;
end;

// Close running instance before uninstallation starts
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec('taskkill.exe', '/F /IM "{#MyAppExeName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(500);
  end;
end;
