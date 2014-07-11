@set SRC=C:\bci2000-svn\3.x\prog
copy %SRC%\BCI2000Shell.exe                       ..\app\prog\
copy %SRC%\Operator.exe                           ..\app\prog\
copy %SRC%\OperatorLib.dll                        ..\app\prog\
copy %SRC%\BCI2000Remote.py                       ..\app\prog\
copy %SRC%\BCI2000RemoteLib.dll                   ..\app\prog\
copy %SRC%\NIDAQ_mx_Source.exe                    ..\app\prog\
copy %SRC%\SignalGenerator.exe                    ..\app\prog\
copy %SRC%\FilePlayback.exe                       ..\app\prog\
copy %SRC%\DummySignalProcessing.exe              ..\app\prog\
copy %SRC%\ReflexConditioningSignalProcessing.exe ..\app\prog\
copy %SRC%\DummyApplication.exe                   ..\app\prog\
@pause
