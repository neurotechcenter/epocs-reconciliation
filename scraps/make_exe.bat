@rd /s /q build > NUL 2> NUL
@rd /s /q dist > NUL 2> NUL

@if "%PYTHONHOME_EPOCS%"=="" goto skipconfig
@set PYTHONHOME=%PYTHONHOME_EPOCS%
@set PATH=%PYTHONHOME%;%PATH%
:skipconfig

@python make_exe.py

@rd /s /q build > NUL 2> NUL

@pause