:: On Windows 7+ you will need to "Run as administrator" rather than just run
:: this file.

:: Note that the changes to environment variables won't be initially recognized. You
:: need to restart, or go to Control Panel->System->Advanced->Environment variables
:: and click OK, or use some binary that "broadcasts a window message", as explained
:: in http://stackoverflow.com/questions/24500881 and
::    http://stackoverflow.com/questions/20653028

@set "PYTHONHOME_EPOCS=C:\FullMonty275\App"
:: TODO: could make this more sensitive

@set /p ANS=Path to parent directory of pythonw.exe (default is %PYTHONHOME_EPOCS%): 
@if "%ANS%" == "" goto skipreplace
@set "PYTHONHOME_EPOCS=%ANS%"
:skipreplace

@set "EnvKey=HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
@echo Adding PYTHONHOME_EPOCS=%PYTHONHOME_EPOCS% to system environment variables:
@reg add "%EnvKey%" /v PYTHONHOME_EPOCS /t REG_SZ /d "%PYTHONHOME_EPOCS%

@echo You will have to open Windows' "Environment Variables" window and press "OK" for the change to be recognized.

@pause
@SystemPropertiesAdvanced
