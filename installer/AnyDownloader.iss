; AnyDownloader Windows installer (Inno Setup 7)
#define AppName "AnyDownloader"
#define AppVersion "1.0.5"
#define AppPublisher "Shishir Islam"
#define AppURL "https://github.com/Shishir-ip/AnyDownloader"
#define AppExe "AnyDownloader.exe"

[Setup]
AppId={{8E6B42A1-7C55-4F0E-9E1D-AnyDownloader2026}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\build\installer
OutputBaseFilename=AnyDownloader-Setup-{#AppVersion}
SetupIconFile=..\assets\app.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\build\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\extension\*"; DestDir: "{app}\browser-extension"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
; anydownloader:// URL protocol so the browser extension can cold-start the app
Root: HKCR; Subkey: "anydownloader"; ValueType: string; ValueData: "URL: AnyDownloader protocol"; Flags: uninsdeletekey
Root: HKCR; Subkey: "anydownloader"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCR; Subkey: "anydownloader\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExe},0"
Root: HKCR; Subkey: "anydownloader\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; runtime leftovers inside the install dir (none expected, but be tidy)
Type: files; Name: "{app}\*.log"
