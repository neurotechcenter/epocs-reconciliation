@if "%PYTHONHOME_EPOCS%"=="" goto skipconfig
@set PYTHONHOME=%PYTHONHOME_EPOCS%
@set PATH=%PYTHONHOME%;%PATH%
:skipconfig
@start python epocs.py --offline
::--log=../../offline-logs/offline-###.txt
