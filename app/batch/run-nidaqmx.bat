#!../prog/BCI2000Shell
@cls & ..\prog\BCI2000Shell %0 %* #! && exit /b 0 || exit /b 1

system taskkill /F /FI "IMAGENAME eq NIDAQ_mx_Source.exe"
system taskkill /F /FI "IMAGENAME eq ReflexConditioningSignalProcessing.exe"
system taskkill /F /FI "IMAGENAME eq DummyApplication.exe"

change directory $BCI2000LAUNCHDIR
set environment MODE master 
if [ $1 ]; set environment MODE $1; end
if [ $MODE == master ]; show window; end
set title ${extract file base $0}
reset system
startup system localhost

start executable NIDAQ_mx_Source                    --local
start executable ReflexConditioningSignalProcessing --local --LogDigiOut=Dev1-000000010000000000000000 --LogAnaOut=Dev1-10 --NumberOfThreads=1
start executable DummyApplication                   --local

add parameter Storage:Session                        string   SessionStamp=           %     %  % % // 
add parameter Application:Operant%20Conditioning     string   ApplicationMode=       ST     %  % % // 
add parameter Application:Operant%20Conditioning     float    BackgroundScaleLimit=  20mV 20mV 0 % // 
add parameter Application:Operant%20Conditioning     float    ResponseScaleLimit=    20mV 20mV 0 % // 
add parameter Application:Operant%20Conditioning     float    BaselineResponseLevel=  %    8mV 0 % //

wait for connected

load parameterfile ../parms/base-nidaqmx.prm

if [ $MODE == master ]
	setconfig
	set state Running 1
else
	set parameter OutputMode 0
	set parameter VisualizeRangeIntegrator 0

	set parameter VisualizeTiming 0
	set parameter VisualizeSource 0
	set parameter VisualizeTrapFilter 0
	set parameter VisualizeBackgroundAverages 0
end