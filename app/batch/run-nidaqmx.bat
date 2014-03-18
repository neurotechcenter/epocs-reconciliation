#!../prog/BCI2000Shell
@cls & ..\prog\BCI2000Shell %0 %* #! && exit /b 0 || exit /b 1

system taskkill /F /FI "IMAGENAME eq NIDAQ_mx_Source.exe"
system taskkill /F /FI "IMAGENAME eq FilePlayback.exe"
system taskkill /F /FI "IMAGENAME eq ReflexConditioningSignalProcessing.exe"
system taskkill /F /FI "IMAGENAME eq DummyApplication.exe"

change directory $BCI2000LAUNCHDIR
set environment MODE master 
if [ $1 ]; set environment MODE $1; end
if [ $MODE == master ]; show window; end
set title ${extract file base $0}
reset system
startup system localhost

set environment DEVEL $2

if [ $DEVEL ]
	start executable FilePlayback                       --local --EvaluateTiming=0 --PlaybackFileName=../../data/sample/akt-2014-01-30-14-25-R11-TT.dat
	start executable ReflexConditioningSignalProcessing --local --NumberOfThreads=1
	start executable DummyApplication                   --local
else
	start executable NIDAQ_mx_Source                    --local
	start executable ReflexConditioningSignalProcessing --local --NumberOfThreads=1 --LogDigiOut=Dev1-000000010000000000000000 --LogAnaOut=Dev1-10
	start executable DummyApplication                   --local
end

add parameter Storage:Session                        string   SessionStamp=           %     %  % % // 
add parameter Application:Operant%20Conditioning     string   ApplicationMode=       ST     %  % % // 
add parameter Application:Operant%20Conditioning     float    BackgroundScaleLimit=  20mV 20mV 0 % // 
add parameter Application:Operant%20Conditioning     float    ResponseScaleLimit=    20mV 20mV 0 % // 
add parameter Application:Operant%20Conditioning     float    BaselineResponseLevel=  %    8mV 0 % //

wait for connected

if [ $DEVEL ]
	# do nothing - just use the parameters from the file (vital for SamplingRate and SourceCh*, and desirable for SampleBlockSize - but note that epocs.py may overrule many parameters)
else
	load parameterfile ../parms/base-nidaqmx.prm
	if ${is file ../parms/custom.prm} ; load parameterfile ../parms/custom.prm ; end
end

if [ $MODE == master ]
	set parameter VisualizeTiming 1
	set parameter VisualizeSource 1
	set parameter VisualizeTrapFilter 1
	set parameter VisualizeBackgroundAverages 1
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