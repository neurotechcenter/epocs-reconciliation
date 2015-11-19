@echo off
for /F "usebackq tokens=1,2 delims==" %%i in (`wmic os get LocalDateTime /VALUE 2^>NUL`) do if '.%%i.'=='.LocalDateTime.' set DATETIMESTAMP=%%j
set "YYYYMMDD=%DATETIMESTAMP:~0,8%
set   "HHMMSS=%DATETIMESTAMP:~8,6%
set "HGLOGFILE=system-logs\%YYYYMMDD%-%HHMMSS%-update.txt
@echo on

hg pull --update
:: TODO: would be nice to have a copy of the pull log on file too but Windows has no tee

@hg log -v -G -l 4 > %HGLOGFILE%
@pause
