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
OutputBaseFilename=Install-DigitimerControljen
SetupIconFile=.\gui\epocs.ico
Compression=lzma
SolidCompression=yes
OutputDir={#UserProfile}\Desktop
UsePreviousAppDir=no
CreateUninstallRegKey=no
UpdateUninstallLogAppName=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Digitimer Control with Automation";
Name: "digitimer"; Description: "Digitimer Control without Automation";
                                                     
[Components]
Name: "Digitimer"; Description: "DS5/DS8 Add-on"; Types: full digitimer
Name: "DS5"; Description: "DS5 Control"; Types: full digitimer
Name: "Automation"; Description: "Automated Control"; Types: full 

[Files]
Source: "gui\DependantClasses\CurrentControl*"; DestDir: "{app}\app\gui\DependantClasses"; Flags: ignoreversion; Components: Digitimer 
Source: "gui\DependantClasses\DS5LibClass*"; DestDir: "{app}\app\gui\DependantClasses"; Flags: ignoreversion; Components: DS5
Source: "gui\DependantClasses\Interop.DS5Lib.dll"; DestDir: "{app}\app\gui-bin"; Flags: ignoreversion; Components: DS5
Source: "gui\DependantClasses\StimulusControl\*"; DestDir: "{app}\app\gui\DependantClasses\StimulusControl"; Flags: ignoreversion; Components: Automation
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Run]
Filename: {app}\app\prog\DS5Setup.exe; Description: Install DS5 drivers; Flags: postinstall skipifsilent
Filename: {app}\app\prog\DS8R-Install-1.2.0.0.exe; Description: Install DS8 drivers; Flags: postinstall skipifsilent
Filename: {app}\app\NISetup\NIAnalogOutput.exe; Description: Setup NI Analog Output Ports; Flags: postinstall skipifsilent



