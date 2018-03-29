////////////////////////////////////////////////////////////////////////////////
// Authors:
// Description: D188ControlFilter implementation
// Filter uses the NI board to set an output 
////////////////////////////////////////////////////////////////////////////////

#include "stdafx.h"
#include "stdlib.h"
#include <iostream>
#include "D188ControlFilter.h"
#include "BCIStream.h"

using namespace std;

RegisterFilter( D188ControlFilter, 2.E );

D188ControlFilter::D188ControlFilter()
{
}

D188ControlFilter::~D188ControlFilter()
{
  Halt();
}

void
D188ControlFilter::Publish()
{
  // Define any parameters that the filter needs....

 BEGIN_PARAMETER_DEFINITIONS

   "Filtering:D188ControlFilter int EnableD188ControlFilter= 0 0 0 1 // enable D188ControlFilter? (boolean)",
   "Filtering:D188ControlFilter int D188StartChannel= 4 0 0 8 // Initial channel to use if D188 Enabled",
   "Filtering:D188ControlFilter	int	D188NIport= "
		" 1 { Device%20Name Port}   "
		"	Dev2       port2        ",
		" % % % // specification for D188 Digital Output",


 END_PARAMETER_DEFINITIONS

 BEGIN_STATE_DEFINITIONS
	"D188Channel  4 0 0 0",  // Value represented as uA so we have 0-65535uA (or 65.535mA max)
 END_STATE_DEFINITIONS


}

int 
D188ControlFilter::ParseMatrix(
	std::string		    & DigitalDeviceName,
	std::string			& AnalogPortSpec,
	std::string			& DigitalPortSpec) const
{

	string paramName = "D188NIport";
	ParamRef matrix = Parameter( paramName);

	if( matrix->NumRows() != 1)
		bcierr << paramName << " parameter must have 1 row" << endl;
	if( matrix->NumColumns() != 2 )
		bcierr << paramName << " parameter must have 2 columns" << endl;

	for( int row = 0; row < matrix->NumRows(); row++ )
	{
		int col = -1;

		string deviceName = StringUtils::Strip( matrix( row, ++col ));
		DigitalDeviceName = deviceName;

		string PortSpec = StringUtils::ToLower(StringUtils::Strip( matrix( row, ++col )));


	}


}



void
D188ControlFilter::Preflight( const SignalProperties& Input, SignalProperties& Output ) const
{
 
  Output = Input; // this simply passes information through about SampleBlock dimensions, etc...
  
  bool iD188 = Parameter("EnableD188ControlFilter");
  
  if (iD188)
  {
	  TaskHandle task;
	  uInt8 tempData = 0x0;

	  if( ReportError( DAQmxCreateTask( "Digital_Output", &task ) ) < 0 )
		  bcierr << "Unable to create task \"Digital_Output\" " << endl;



	  if( ReportError( DAQmxCreateDOChan( task, DigitalPortSpec.c_str(), "", DAQmx_Val_ChanForAllLines ) ) < 0 )
		  bcierr << "Unable to create channel operating on the following lines: " << DigitalPortSpec.c_str() << endl;

	  ReportError (DAQmxWriteDigitalU8(task,1,1,10.0,DAQmx_Val_GroupByChannel,&tempData,NULL,NULL));

	  if( ReportError( DAQmxClearTask( task ) ) < 0 )
			bcierr << "Failed to clear task \"Digital_Output\" " << endl;

	  
  }
  
  



}


void
D188ControlFilter::Initialize( const SignalProperties& Input, const SignalProperties& Output )
{
  
}

void
D188ControlFilter::StartRun()
{

}


void
D188ControlFilter::Process( const GenericSignal& Input, GenericSignal& Output )
{

    Output = Input; // Pass the signal through unmodified.
}

void
D188ControlFilter::StopRun()
{

}

void
D188ControlFilter::Halt()
{

}

// Report any NIDAQmx Errors that may occur //
int
D188ControlFilter::ReportError( int errCode ) const
{
	if( DAQmxFailed( errCode ) ) // if the error code denotes that there is indeed an error, report it
	{
		char buffer[ 2048 ];
		DAQmxGetExtendedErrorInfo( buffer, 2048 );
		bcierr << "NIDAQ Error: " << buffer << endl;
		return errCode; // SOMETHING WENT WRONG HERE
	}
	return 1; // EVERYTHING IS OKAY
}

