#include "..\build\version.iss"
#define InstallId "ParCom.ZnunyAnalytics"
#define InstallName AppName
#ifdef ValidationInstall
  #undef InstallId
  #define InstallId "ParCom.ZnunyAnalytics.Validation"
  #undef InstallName
  #define InstallName AppName + " Installationstest"
#endif
#define ExecutableName "ParCom Znuny Analytics.exe"

[Setup]
AppId={#InstallId}
AppName={#InstallName}
AppVersion={#AppVersion}
AppVerName={#InstallName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Installation
DefaultDirName={autopf}\ParCom\{#InstallName}
DefaultGroupName={#InstallName}
DisableDirPage=no
DisableWelcomePage=no
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\release
OutputBaseFilename=ParCom_Znuny_Analytics_Setup_{#AppVersion}
SetupIconFile=..\assets\app_icon.ico
UninstallDisplayIcon={app}\{#ExecutableName}
UninstallDisplayName={#InstallName}
WizardStyle=modern dark
WizardImageFile=..\build\wizard.bmp
WizardImageStretch=yes
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Verknüpfungen:"; Flags: unchecked

[Files]
Source: "..\dist\web\ParCom_Analytics_Web\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Replace only managed runtime folders to prevent stale Qt/DLL contamination.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\pdf_worker"
Type: files; Name: "{app}\ParCom_Znuny_Analytics.exe"

[Icons]
Name: "{group}\{#InstallName}"; Filename: "{app}\{#ExecutableName}"; AppUserModelID: "{#InstallId}"
Name: "{group}\{#InstallName} deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#InstallName}"; Filename: "{app}\{#ExecutableName}"; Tasks: desktopicon; AppUserModelID: "{#InstallId}"

[Run]
Filename: "{app}\{#ExecutableName}"; Description: "{#AppName} starten"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Intentionally no LOCALAPPDATA entries: local datasets survive uninstallation.

[Messages]
StatusExtractFiles=Anwendungsdateien und Laufzeitkomponenten werden installiert …
StatusCreateIcons=Verknüpfungen werden erstellt …

[Code]
function HasWebView2(RootKey: Integer): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey,
    'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  RuntimeAvailable: Boolean;
begin
  Result := '';
  RuntimeAvailable := HasWebView2(HKLM32) or HasWebView2(HKCU);
#ifdef ValidationInstall
  { Exercise the missing-runtime path without changing the machine registry. }
  if ExpandConstant('{param:ValidateMissingWebView|0}') = '1' then
    RuntimeAvailable := False;
#endif
  if not RuntimeAvailable then
    Result := 'Microsoft Edge WebView2 Runtime fehlt. Installieren Sie die Evergreen Runtime von ' +
      'https://developer.microsoft.com/microsoft-edge/webview2/ und starten Sie danach diese Installation erneut.';
end;

procedure InitializeWizard;
begin
  WizardForm.WizardSmallBitmapImage.Visible := False;
end;
