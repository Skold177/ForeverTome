#define AppVersion "0.1.0"
#ifndef BundleDir
  #define BundleDir AddBackslash(SourcePath) + "..\dist\exporter"
#endif

[Setup]
AppId={{6104FC3B-C73E-4434-AE89-BDFE536291B3}
AppName=ForeverTome Exporter
AppVersion={#AppVersion}
AppPublisher=ForeverTome
AppPublisherURL=https://github.com/Skold177/ForeverTome
DefaultDirName={localappdata}\Programs\ForeverTomeExporter
DefaultGroupName=ForeverTome Exporter
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=ForeverTomeSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile={#BundleDir}\LICENSE
UninstallDisplayIcon={app}\ForeverTomeExporter.exe
CloseApplications=no
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#BundleDir}\ForeverTomeExporter.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\ForeverTome Exporter"; Filename: "{app}\ForeverTomeExporter.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\ForeverTome Exporter"; Filename: "{app}\ForeverTomeExporter.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\ForeverTomeExporter.exe"; Description: "Open ForeverTome Exporter to install or update the addon"; Flags: nowait postinstall skipifsilent
