@if "%PYTHONHOME_EPOCS%"=="" goto skipconfig
@set PYTHONHOME=%PYTHONHOME_EPOCS%
@set PATH=%PYTHONHOME%;%PATH%
:skipconfig
@start pythonw epocs.py --log=../../system-logs/###-python.txt %*
::python epocs.py --log=../../system-logs/###-python.txt %*
