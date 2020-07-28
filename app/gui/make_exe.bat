@rd /s /q build > NUL 2> NUL
@rd /s /q dist > NUL 2> NUL

@if "%PYTHONHOME_EPOCS%"=="" goto SkipConfig
@set PYTHONHOME=C:\PYTHON27   
REM %PYTHONHOME_EPOCS%
@set PATH=%PYTHONHOME%;%PATH%
@echo Running Python from %PYTHONHOME%
:SkipConfig

@where python
@python make_exe.py

@rd /s /q build > NUL 2> NUL

@echo Moving directory into place
@dir ..\gui-bin > NUL 2> NUL && ( rd /s /q ..\gui-bin > NUL || goto SkipToTheEnd )
move dist ..\gui-bin

:SkipToTheEnd
@pause
