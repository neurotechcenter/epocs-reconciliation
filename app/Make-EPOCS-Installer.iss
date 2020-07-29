; Script generated by the Inno Setup Script Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

#define MyAppName "EPOCSjen"
#define MyAppVersion "4.8"  
#define MyAppPublisher "Translational Neurological Research Laboratory"
#define UserProfile GetEnv('USERPROFILE')
[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{F7C88855-3358-4D9A-80B3-374D53AA859E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
;AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={sd}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir={#UserProfile}\Desktop
OutputBaseFilename=Install-EPOCSjen
SetupIconFile=.\gui\epocs.ico
Compression=lzma
SolidCompression=yes
UsePreviousAppDir=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Types]
Name: "full"; Description: "EPOCS + add-ons (Mwave Tool)";
Name: "epocs"; Description: "EPOCS only";
Name: "mwave"; Description: "Mwave Tool";
                                                     
[Components]
Name: "epocs"; Description: "EPOCS"; Types: epocs full
Name: "mwave"; Description: "Mwave Tool"; Types: mwave full

[Files]
Source: "..\*";             DestDir: "{app}";             Excludes:"\data,\system-logs,.ini,.log,.mmap,.pyc,app\parms\NIDigitalOutputPort.prm,\app\gui\DependantClasses\CurrentControl*,\app\gui\DependantClasses\MwaveAnalysisClass*,\app\gui\DependantClasses\StimulusControl,\app\gui\DependantClasses\DS5LibClass*,\app\gui\DependantClasses\Interop.DS5Lib.dll,\app\gui-bin\Interop.DS5Lib.dll"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: epocs 
Source: "..\data\sample\*"; DestDir: "{app}\data\sample";                                                     Flags: ignoreversion recursesubdirs createallsubdirs     ; Components: epocs
Source: "gui\DependantClasses\MwaveAnalysisClass*"; DestDir: "{app}\app\gui\DependantClasses"; Flags: ignoreversion; Components: mwave 
Source: "prog\NIDAQ1551f0_downloader.exe."; DestDir: "{app}\app\prog\"; Flags: ignoreversion
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Run]
Filename: {app}\app\prog\vcredist_x86.exe; Description: Visual Studio 2012 Redistributable; Flags: postinstall skipifsilent; Check: "not IsWin64"
Filename: {app}\app\prog\vcredist_x64.exe; Description: Visual Studio 2012 Redistributable; Flags: postinstall skipifsilent; Check: IsWin64
;Filename: {app}\app\prog\NIDAQ1551f0_downloader.exe; Description: Install NIDAQmx 15.5; Flags: postinstall skipifsilent
Filename: {app}\app\NISetup\NIDigitalOutput.exe; Description: Setup NI Device Output Ports; Flags: postinstall skipifsilent

[Dirs]
Name: "{app}"; Permissions: users-modify

[Icons]
Name: "{group}\EPOCS";                          Filename: "{app}\app\gui-bin\epocs.exe"
Name: "{group}\EPOCS Offline Analysis";         Filename: "{app}\app\gui-bin\epocs-offline.exe"
Name: "{group}\EPOCS Data Directory";           Filename: "{app}\data"
Name: "{commondesktop}\EPOCS";                  Filename: "{app}\app\gui-bin\epocs.exe";         Tasks: desktopicon
Name: "{commondesktop}\EPOCS Offline Analysis"; Filename: "{app}\app\gui-bin\epocs-offline.exe"; Tasks: desktopicon
Name: "{commondesktop}\EPOCS Data Directory";   Filename: "{app}\data";                          Tasks: desktopicon

[UninstallDelete]
Type: files; Name: "{app}\app\gui\epocs.ini"
Type: files; Name: "{app}\app\gui-bin\epocs.ini"
Type: files; Name: "{app}\app\gui-bin\epocs.exe.log"
Type: files; Name: "{app}\app\prog\BCI2000Remote.pyc"
Type: files; Name: "{app}\app\prog\Operator.ini"
Type: files; Name: "{app}\app\prog\epocs.mmap"

[Code]
function InitializeSetup: boolean;
var
  ResultCode: Integer;
begin
  Result := RegKeyExists(HKEY_LOCAL_MACHINE,'SOFTWARE\Wow6432Node\National Instruments\NI-DAQmx\CurrentVersion')
  if not Result then
    begin
    if MsgBox('National Instruments NIDAQmx not found. Please re-run EPOCS installation after installing NIDAQmx. Install version 15.5 now? ', mbConfirmation, MB_YESNO) = IDYES then
      
      ExtractTemporaryFile('NIDAQ1551f0_downloader.exe');
      ExecAsOriginalUser( ExpandConstant('{tmp}\NIDAQ1551f0_downloader.exe'), '', '', SW_SHOWNORMAL, ewNoWait, ResultCode)
    Result := False;
    end
end;


