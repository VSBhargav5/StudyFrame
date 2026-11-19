; Per-user unsigned installer. Build only from a verified portable bundle.
#ifndef AppVersion
  #error AppVersion is required
#endif
[Setup]
AppId={{FFCB9E40-5FEC-4C99-90B4-0B2C60BE1995}
AppName=StudyFrame
AppVersion={#AppVersion}
AppPublisher=Bhargav Vasireddy
DefaultDirName={localappdata}\Programs\StudyFrame
DefaultGroupName=StudyFrame
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
AppMutex=Local\StudyFrame.Application
CloseApplications=no
RestartApplications=no
OutputDir={#StageDir}
OutputBaseFilename=StudyFrame-{#AppVersion}-windows-x64-setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\StudyFrame.exe
DisableProgramGroupPage=yes
[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\StudyFrame"; Filename: "{app}\StudyFrame.exe"
; No auto-run, registry credential entries or user-data deletion on uninstall.
