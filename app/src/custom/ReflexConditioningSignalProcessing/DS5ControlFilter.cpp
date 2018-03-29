////////////////////////////////////////////////////////////////////////////////
// Authors:
// Description: DS5ControlFilter implementation
////////////////////////////////////////////////////////////////////////////////

#include "stdafx.h"
#include "stdlib.h"
#include <iostream>
#include "DS5ControlFilter.h"
#include "BCIStream.h"

using namespace std;

RegisterFilter( DS5ControlFilter, 2.D );

DS5ControlFilter::DS5ControlFilter()
{
}

DS5ControlFilter::~DS5ControlFilter()
{
  Halt();
  if (DS8Controller.ErrorCode == 0)
  {  DS8Controller.CloseDS8(); }
}

void
DS5ControlFilter::Publish()
{
  // Define any parameters that the filter needs....

 BEGIN_PARAMETER_DEFINITIONS
	
   "Filtering:DS8ControlFilter int EnableDS5ControlFilter= 0 0 0 1 // enable DS5ControlFilter? (boolean)",
   "Filtering:DS8ControlFilter int EnableDS8ControlFilter= 0 0 0 1 // enable DS8ControlFilter? (boolean)",

 END_PARAMETER_DEFINITIONS

 BEGIN_STATE_DEFINITIONS

	"DS5CommStatus   1 0 0 0",  // Value represented as uA so we have 0-65535uA (or 65.535mA max)
END_STATE_DEFINITIONS


}

void
DS5ControlFilter::Preflight( const SignalProperties& Input, SignalProperties& Output ) const
{
 
  Output = Input; // this simply passes information through about SampleBlock dimensions, etc...
  DS8library::DS8Functions DS8;
  bool iDS5 = Parameter("EnableDS5ControlFilter");
  bool iDS8 = Parameter("EnableDS8ControlFilter");

  if ((iDS5) & (iDS8))
  {
	  bcierr << "Cannot enable both the DS5 and DS8, please select one or the other" << endl;
  }

  if (iDS8)
  {
	  if (DS8.ErrorCode == 1)
	  {
		  bcierr << "Unable to load DS8 library. Make sure the DS8 is on, and the DS8 software has been installed." << endl;
	  }
  }

  
  double PulseWidth = Parameter( "PulseWidth" ).InMilliseconds()*1000; //***

  if( (PulseWidth < 50) && (PulseWidth > 2000)) //***
  {
	bciwarn << "Warning: Pulse Width is " << PulseWidth << ", which is outside the 0.5-1ms used for H-reflex conditioning" << std::endl;
  }

  int StimType = Parameter("StimulationType"); //***
  int UpdateState = State("NeedsUpdating");
  int CurrentAmplitude = State("CurrentAmplitude");
  float InitialCurrent = Parameter("InitialCurrent");



}


void
DS5ControlFilter::Initialize( const SignalProperties& Input, const SignalProperties& Output )
{
  
  enableDS8 = Parameter("EnableDS8ControlFilter");

  if (enableDS8)
  {
	  if (DS8Controller.ErrorCode == -1)
	  {
		   bcierr << "Unable to load DS8 library. Make sure the DS8 is on, and the DS8 software has been installed." << endl;
	  }
	  else
	  {
		  int StimulationType = Parameter("StimulationType");
		  float PulseWidth = Parameter("PulseWidth").InMilliseconds()*1000; 
		  float Current = Parameter("InitialCurrent")*10;

		  //Defaults to Mode=2 (bipolar), polarity=2 (Negative), Current=0,width=500,recovery=100%,dwell=1us.
		  DS8Controller.SetVariables(StimulationType,NULL,Current,PulseWidth,NULL,NULL,TRUE);
	  }

  }


}

void
DS5ControlFilter::StartRun()
{

	if ( enableDS8 & (DS8Controller.ErrorCode == 0))	
	{
		DS8Controller.ToggleOutput(TRUE);
	}

}


void
DS5ControlFilter::Process( const GenericSignal& Input, GenericSignal& Output )
{

    Output = Input; // Pass the signal through unmodified.
	bool Update = State("NeedsUpdating");
	
	if (enableDS8 & Update & (DS8Controller.ErrorCode == 0))
	{
		
		int val = State("CurrentAmplitude")/100;
		//bciwarn << "Current:" << std::to_string(val) << endl;
		DS8Controller.SetVariables(NULL,NULL,val,NULL,NULL,NULL,TRUE);
		State("NeedsUpdating") = 0;
	}

}

void
DS5ControlFilter::StopRun()
{
	if (enableDS8 & (DS8Controller.ErrorCode == 0))
	{
		DS8Controller.ToggleOutput(FALSE);
	}

}

void
DS5ControlFilter::Halt()
{

}
