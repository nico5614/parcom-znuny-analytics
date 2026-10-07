#include "..\build\version.iss"

[Setup]
AppId=ParCom.ZnunyAnalytics
AppName={#AppName}
AppVersion={#DisplayVersion}
AppVerName={#AppName} {#DisplayVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Installation
DefaultDirName={autopf}\ParCom\ParCom Znuny Analytics
DefaultGroupName={#AppName}
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
UninstallDisplayIcon={app}\ParCom_Znuny_Analytics.exe
UninstallDisplayName={#AppName}
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
Source: "..\dist\ParCom_Znuny_Analytics\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\ParCom_Znuny_Analytics.exe"; AppUserModelID: "ParCom.ZnunyAnalytics"
Name: "{group}\{#AppName} deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\ParCom_Znuny_Analytics.exe"; Tasks: desktopicon; AppUserModelID: "ParCom.ZnunyAnalytics"

[Run]
Filename: "{app}\ParCom_Znuny_Analytics.exe"; Description: "{#AppName} starten"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Intentionally no LOCALAPPDATA entries: local datasets survive uninstallation.

[Messages]
StatusExtractFiles=Anwendungsdateien und Laufzeitkomponenten werden installiert …
StatusCreateIcons=Verknüpfungen werden erstellt …

[Code]
procedure InitializeWizard;
begin
  WizardForm.WizardSmallBitmapImage.Visible := False;
end;
