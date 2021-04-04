////////////////////////////////////////////////////////////////////////////////
// Authors:
// Description: DigitimerFilter implementation
// Filter uses the NI board to set an output 
////////////////////////////////////////////////////////////////////////////////

#include "stdafx.h"
#include "stdlib.h"
#include <iostream>
#include "DigitimerFilter.h"
#include "BCIStream.h"

using namespace std;

RegisterFilter( DigitimerFilter, 2.D );

DigitimerFilter::DigitimerFilter()
{

}

DigitimerFilter::~DigitimerFilter()
{
  Halt();
  if (DS8Controller.ErrorCode == 0)
  {  DS8Controller.CloseDS8(); }
}

void
DigitimerFilter::Publish()
{
  // Define any parameters that the filter needs....

 BEGIN_PARAMETER_DEFINITIONS

   "Stimulation:DigitimerFilter int EnableD188ControlFilter= 0 0 0 1 // enable DigitimerFilter? (boolean)",
   "Stimulation:DigitimerFilter int EnableDS5ControlFilter= 0 0 0 1 // enable DS5ControlFilter? (boolean)",
   "Stimulation:DigitimerFilter int EnableDS8ControlFilter= 0 0 0 1 // enable DS8ControlFilter? (boolean)",
   "Stimulation:DigitimerFilter int D188Channel= 1 0 0 8 // Initial channel to use if D188 Enabled",
  
 END_PARAMETER_DEFINITIONS

}


void
DigitimerFilter::Preflight( const SignalProperties& Input, SignalProperties& Output ) const
{
 
  Output = Input; // this simply passes information through about SampleBlock dimensions, etc...
  bool iD188 = Parameter("EnableD188ControlFilter");
  int Channel = Parameter("D188Channel");
  bool iDS5 = Parameter("EnableDS5ControlFilter");
  bool iDS8 = Parameter("EnableDS8ControlFilter");

  DS8library::DS8Functions DS8;

  
  if ( iD188 )
  {  
	D188library::D188Functions D188;
	
	if ((Channel < 1) | (Channel > 8))
	{
		bcierr << "Initial channel set to " << to_string(Channel) << ". Must be an integer from 1 to 8" << endl;
	}
  }

  
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
DigitimerFilter::Initialize( const SignalProperties& Input, const SignalProperties& Output )
{		
	iD188 = Parameter("EnableD188ControlFilter");
	Channel = Parameter("D188Channel");

	if (iD188)
	{
		if ((Channel < 1) | (Channel > 8))
		{
			bcierr << "Initial channel set to " << to_string(Channel) << ". Must be an integer from 1 to 8" << endl;
		}

		if (D188Controller.ErrorCode == -1)
		{
			bcierr << "Unable to load D188 library. Make sure the D188 is on, and the D188 software has been installed." << endl;
		}
		else
		{
			D188Controller.SetChannel(Channel);
		}

	}
	  
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
			DS8Controller.SetVariables(StimulationType,NULL,Current,PulseWidth,NULL,NULL,true);
		}

	}

}

void
DigitimerFilter::StartRun()
{
	if ( enableDS8 & (DS8Controller.ErrorCode == 0))	
	{
		DS8Controller.ToggleOutput(TRUE);
	}
}


void
DigitimerFilter::Process( const GenericSignal& Input, GenericSignal& Output )
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
DigitimerFilter::StopRun()
{
	if (enableDS8 & (DS8Controller.ErrorCode == 0))
	{
		DS8Controller.ToggleOutput(FALSE);
	}
}

void
DigitimerFilter::Halt()
{
}
