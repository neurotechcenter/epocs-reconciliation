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
   "Filtering:D188ControlFilter int D188Channel= 1 0 0 8 // Initial channel to use if D188 Enabled",
  
 END_PARAMETER_DEFINITIONS

}


void
D188ControlFilter::Preflight( const SignalProperties& Input, SignalProperties& Output ) const
{
 
  Output = Input; // this simply passes information through about SampleBlock dimensions, etc...
  bool iD188 = Parameter("EnableD188ControlFilter");
  int Channel = Parameter("D188Channel");

  
  if ( iD188 )
  {  
	D188library::D188Functions D188;
	if ((Channel < 1) | (Channel > 8))
	{
		bcierr << "Initial channel set to " << to_string(Channel) << ". Must be an integer from 1 to 8" << endl;
	}
  }


}


void
D188ControlFilter::Initialize( const SignalProperties& Input, const SignalProperties& Output )
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
	  
}

void
D188ControlFilter::StartRun()
{
	//if ((iD188) & (D188Controller.ErrorCode != -1))
	//{
	//	D188Controller.SetChannel(Channel);
	//}
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
