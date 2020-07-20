@echo off
for /F "usebackq tokens=1,2 delims==" %%i in (`wmic os get LocalDateTime /VALUE 2^>NUL`) do if '.%%i.'=='.LocalDateTime.' set DATETIMESTAMP=%%j
set "YYYYMMDD=%DATETIMESTAMP:~0,8%
set   "HHMMSS=%DATETIMESTAMP:~8,6%
set "HGLOGFILE=system-logs\%YYYYMMDD%-%HHMMSS%-update.txt
mkdir system-logs 2>NUL
set "HGURL=http://tortoisehg.bitbucket.org/download
where hg 2>NUL>NUL || echo To enable automatic updates, install an hg client like TortoiseHG ^
                   && echo. ^
                   && echo If you like I'll take you to %HGURL% now^
                   && pause ^
                   && start %HGURL% ^
                   && goto :eof
@echo on

hg pull https://bitbucket.org/jezhill/epocs --update > "%HGLOGFILE%
@type "%HGLOGFILE%
:: TODO: would be nice to have a copy of the pull log on file too but Windows has no tee utility

@hg log -v -G -l 4 >> %HGLOGFILE%
@pause
