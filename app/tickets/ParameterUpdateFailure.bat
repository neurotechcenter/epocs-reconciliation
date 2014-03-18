#!../prog/BCI2000Shell
@cls & ..\prog\BCI2000Shell %0 %* #! && exit /b 0 || exit /b 1

set environment STARTDIR ${current directory}
change directory $BCI2000LAUNCHDIR
show window
set title ${extract file base $0}
reset system
startup system localhost

start executable SignalGenerator       --local
start executable DummySignalProcessing --local
start executable DummyApplication      --local

wait for connected

set parameter SubjectName Zark
set parameter DataDirectory $STARTDIR

set parameter DataFile %24{SubjectName}-Foo-S%24{SubjectSession}R%24{SubjectRun}.%24{FileFormat}
setconfig
#set title Foo ; set state Running 1 ; sleep 5; set state Running 0; wait for suspended     # CRITICAL

set parameter DataFile %24{SubjectName}-Bar-S%24{SubjectSession}R%24{SubjectRun}.%24{FileFormat}
setconfig
warn DataFile= ${get parameter DataFile}
set title Bar ; set state Running 1 ; sleep 5; set state Running 0; wait for suspended

quit


#  If the line marked # CRITICAL is included (uncommented), then all is well.
#  However, unexpected behaviour occurs if you comment this line out,
#  i.e. if you set the DataFile parameter and setconfig, but then
#  try to update the DataFile parameter to another value and setconfig
#  again without actually recording a run using the first ("Foo") settings.
#  What happens is that, although DataFile appears to have been updated
#  (the warning message correctly contains Bar, not Foo) the update is not
#  recognized for the purpose of determining the file name: the data file
#  is still recorded with "Foo", not "Bar" in the filename.
#
#  NB the same trouble happens if DataFile itself is not changed from one
#  setconfig to the next, but contains a reference to a Parameter ${Whatever},
#  which does change:  the change recognized by the system at some level (i.e.
#  is correct when queried by get parameter), but not implemented in determining
#  the filename.