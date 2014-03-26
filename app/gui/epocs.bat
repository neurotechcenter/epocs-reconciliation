@if "%EPOCS_PYTHON%"=="" goto skipconfig
@set PYTHONHOME=%EPOCS_PYTHON%
@set PATH=%PYTHONHOME%;%PATH%
:skipconfig
@start pythonw epocs.py --log=../../system-logs/epocs-log-###.txt