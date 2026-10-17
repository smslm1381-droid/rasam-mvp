#ifndef BundleDir
  #error BundleDir is required
#endif
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif

[Setup]
AppId={{B0B76B40-8A3C-43C8-91E2-DF2745B785AF}
AppName=Rasam
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Rasam
DefaultGroupName=Rasam
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=RasamSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Rasam.exe
CloseApplications=yes
RestartApplications=no
InfoBeforeFile=unsigned-notice.txt

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Rasam"; Filename: "{app}\Rasam.exe"
Name: "{autodesktop}\Rasam"; Filename: "{app}\Rasam.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\Rasam.exe"; Description: "Launch Rasam"; Flags: nowait postinstall skipifsilent

; داده‌های AppData و رازهای Windows در حذف یا نصب مجدد دست‌نخورده می‌مانند.
