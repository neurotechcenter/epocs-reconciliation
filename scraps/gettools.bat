@set SRC=C:\bci2000-svn\rollback\tools\cmdline
copy %SRC%\bci_dat2stream.exe           ..\app\tools\cmdline\
copy %SRC%\bci_stream2mat.exe           ..\app\tools\cmdline\
copy %SRC%\TransmissionFilter.exe       ..\app\tools\cmdline\
copy %SRC%\IIRBandpass.exe              ..\app\tools\cmdline\
copy %SRC%\BackgroundTriggerFilter.exe  ..\app\tools\cmdline\
copy %SRC%\TrapFilter.exe               ..\app\tools\cmdline\
copy %SRC%\RangeIntegrator.exe          ..\app\tools\cmdline\
@pause
