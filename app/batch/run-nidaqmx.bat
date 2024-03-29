#!../prog/BCI2000Shell
@cls & ..\prog\BCI2000Shell %0 %* #! && exit /b 0 || exit /b 1

system taskkill /F /FI "IMAGENAME eq NIDAQ_mx_Source.exe"
system taskkill /F /FI "IMAGENAME eq gUSBampSource.exe"
system taskkill /F /FI "IMAGENAME eq FilePlayback.exe"
system taskkill /F /FI "IMAGENAME eq aReflexConditioningSignalProcessing.exe"
system taskkill /F /FI "IMAGENAME eq DummyApplication.exe"

change directory $BCI2000LAUNCHDIR

set environment MODE $1                    # "master" or "slave"
set environment SOURCE $2                  # "replay" or "live"
set environment AMP $3			   		   # empty, or gusbamp if using gusb
set environment CUSTOM $4                  # empty, or a path to a BCI2000 script file
	

if [ $MODE == "master" ]; show window; end
set title ${extract file base $0}
reset system

if [ $EPOCSTIMESTAMP == "" ]; set environment EPOCSTIMESTAMP $YYYYMMDD-$HHMMSS; end
startup system localhost --SystemLogFile=../../system-logs/$EPOCSTIMESTAMP-operator.txt


if [ $SOURCE == "replay" ]
	start executable FilePlayback                       --local --EvaluateTiming=0 --PlaybackFileName=../../data/sample/fcr2l-2016-10-06-11-13-R07-ST.dat
	start executable aReflexConditioningSignalProcessing --local --NumberOfThreads=1
	start executable DummyApplication                   --local
else
	if [ $AMP == "gusbamp" ]
		start executable gUSBampSource                    --local
	else
		start executable NIDAQ_mx_Source                    --local
	end

	start executable DummyApplication                   --local
	SLEEP 1
	start executable aReflexConditioningSignalProcessing --local --NumberOfThreads=1
end

add parameter Storage:Session                        string   SessionStamp=           %     %  % % // 
add parameter Application:Operant%20Conditioning     string   ApplicationMode=       ST     %  % % // 
add parameter Application:Operant%20Conditioning     float    BackgroundScaleLimit=  20mV 20mV 0 % // 
add parameter Application:Operant%20Conditioning     float    ResponseScaleLimit=    20mV 20mV 0 % // 
add parameter Application:Operant%20Conditioning     float    BaselineResponseLevel=  %    8mV 0 % //
add parameter Application:EPOCS                      float    MwaveTarget=  30mV  30mV % % //
add parameter Application:EPOCS                      float    MwavePercentage=  20  20 % % //
add parameter Application:EPOCS                      float    TargetPercentile=  66  66 % % //


wait for connected

if [ $SOURCE == "replay" ]
	Set parameter DigitalOuput 0
    	Set parameter AnalogOutput 0
	# do nothing - just use the parameters from the file (vital for SamplingRate and SourceCh*, and desirable for SampleBlockSize - but note that epocs.py may overrule many parameters)
else
	load parameterfile ../parms/NIDigitalOutputPort.prm	
	if [ $AMP == "gusbamp" ]
		load parameterfile ../parms/base-gUSBamp.prm
	else
		load parameterfile ../parms/base-nidaqmx.prm
	end
end

if [ $MODE == "master" ]
	set parameter VisualizeTiming 1
	set parameter VisualizeSource 1
	set parameter VisualizeBackgroundAverages 1
	set parameter VisualizeTrapFilter 1
	set parameter VisualizeRangeIntegrator 1
else
	set parameter OutputMode 0
end

if [ $CUSTOM ]
	execute script $CUSTOM
end

if [ $MODE == "master" ]
	setconfig 1
	set state Running 1
end
