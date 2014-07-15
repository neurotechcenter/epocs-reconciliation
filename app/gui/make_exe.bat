@rd /s /q build > NUL 2> NUL
@rd /s /q dist > NUL 2> NUL

@if "%PYTHONHOME_EPOCS%"=="" goto skipconfig
@set PYTHONHOME=%PYTHONHOME_EPOCS%
@set PATH=%PYTHONHOME%;%PATH%
@echo Running Python from %PYTHONHOME%
:skipconfig

@python make_exe.py

@rd /s /q build > NUL 2> NUL

@echo Moving directory into place
@rd /s /q ..\gui-bin > NUL || goto skipmove
move dist ..\gui-bin
:skipmove

@pause
