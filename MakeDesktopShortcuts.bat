@cd app\gui-bin || (echo no gui-bin directory && pause && goto SkipShortcuts)
@set SCRIPT="%TEMP%\%RANDOM%-%RANDOM%-%RANDOM%-%RANDOM%.vbs"

@echo Set oWS = WScript.CreateObject("WScript.Shell") >> %SCRIPT%
@echo Set oLink = oWS.CreateShortcut("%USERPROFILE%\Desktop\EPOCS.lnk") >> %SCRIPT%
@echo oLink.TargetPath = "%CD%\epocs.exe" >> %SCRIPT%
@echo oLink.WorkingDirectory = "%CD%" >> %SCRIPT%
@echo oLink.Save >> %SCRIPT%

@echo Set oLink = oWS.CreateShortcut("%USERPROFILE%\Desktop\EPOCS Offline Analysis.lnk") >> %SCRIPT%
@echo oLink.TargetPath = "%CD%\epocs-offline.exe" >> %SCRIPT%
@echo oLink.WorkingDirectory = "%CD%" >> %SCRIPT%
@echo oLink.Save >> %SCRIPT%

@cd ..\..\data
@echo Set oLink = oWS.CreateShortcut("%USERPROFILE%\Desktop\EPOCS Data.lnk") >> %SCRIPT%
@echo oLink.TargetPath = "%CD%" >> %SCRIPT%
@echo oLink.WorkingDirectory = "%CD%" >> %SCRIPT%
@echo oLink.Save >> %SCRIPT%

@cd ..\doc
@echo Set oLink = oWS.CreateShortcut("%USERPROFILE%\Desktop\EPOCS Documentation.lnk") >> %SCRIPT%
@echo oLink.TargetPath = "%CD%\Home.html" >> %SCRIPT%
@echo oLink.WorkingDirectory = "%CD%" >> %SCRIPT%
@echo oLink.Save >> %SCRIPT%

@cscript /nologo %SCRIPT%
@del %SCRIPT%

:: oLink.Arguments
:: oLink.Description
:: oLink.HotKey
:: oLink.IconLocation
:: oLink.WindowStyle
:: oLink.WorkingDirectory

:SkipShortcuts