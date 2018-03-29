////////////////////////////////////////////////////////////////////////////////
// Authors:
// Description: CurrentControlCriteria implementation
////////////////////////////////////////////////////////////////////////////////

#include "CurrentControlCriteria.h"
#include "BCIStream.h"
#include "StringUtils.h"
#include <sstream>
using namespace std;

RegisterFilter( CurrentControlCriteria, 2.G );

CurrentControlCriteria::CurrentControlCriteria()
{
}

CurrentControlCriteria::~CurrentControlCriteria()
{
  Halt();

}

void
CurrentControlCriteria::Publish()
{
  // Define any parameters that the filter needs....

 BEGIN_PARAMETER_DEFINITIONS

   "Stimulation%20Control:Current%20Control%20Criteria int EnableCurrentControl= 0 0 0 1 // enable CurrentControlCriteria? (boolean)",
   "Stimulation%20Control:Current%20Control%20Criteria int NumberOfStimuli= 4 4 1 10 // Number of Stimulii per Current ",
   "Stimulation%20Control:Current%20Control%20Criteria int Criteria=   0  0  0  4 // Options are 0=None 1=Stimulus Test 2=RC Hmax 3=RCMmax 4=Control Trial (enumeration)",

   "Stimulation%20Control:Stimulus%20Test float DeltaCurrent= 1 1 0.25 5// Current Step Size to use in mA",
   "Stimulation%20Control:Stimulus%20Test float ThresholdMultiplier= 4 4 % %// Threshold Multiplier of p2p Background",
   "Stimulation%20Control:Stimulus%20Test float InitialCurrentST= 1 1 % %// Initial Current for ST H-Reflex Test",

 END_PARAMETER_DEFINITIONS

 BEGIN_STATE_DEFINITIONS
	
	"ProcessCompleted 1 0 0 0",

 END_STATE_DEFINITIONS


}

void
CurrentControlCriteria::Preflight( const SignalProperties& Input, SignalProperties& Output ) const
{
	Output=Input;

	//Check the number of Stimuli per Current (default 4)
	int numberStimuli = Parameter("NumberOfStimuli");
	if( (numberStimuli < 1) | (numberStimuli > 10) )
		bcierr << "Number of Stimulii per current should be between 1 and 10, not " << numberStimuli << endl;
	
	//Check the delta currents to be used. 
	ParamRef CurrentSettings = Parameter( "DeltaCurrent");
	double DeltaCurrent = stod(CurrentSettings->Value());
	double minDeltaCurrent = stod(CurrentSettings->LowRange());
	double maxDeltaCurrent = stod(CurrentSettings->HighRange());

	if( DeltaCurrent < minDeltaCurrent)
		bcierr << "Chosen Current Step Size, " << DeltaCurrent << "is too small and should be greater than or equal to " << minDeltaCurrent << endl;

	if( DeltaCurrent > maxDeltaCurrent)
		bcierr << "Chosen Current Step Size, " << DeltaCurrent << "is too large and should be less than or equal to " << maxDeltaCurrent << endl;

	float threshold = Parameter("ThresholdMultiplier");
	if ( (threshold < 0) | (threshold > 50) )
		bcierr << "Chosen threshold multiplier should be between 0 and 50, not" << threshold << endl;

	//Check all the States Used
	if( States->Exists( "TrialsCompleted" ) ) State( "TrialsCompleted" );
	if( States->Exists( "ResponseFeedbackValue" ) ) State( "ResponseFeedbackValue" );
	if( States->Exists( "ReferenceFeedbackValue" ) ) State( "ReferenceFeedbackValue" );
	if( States->Exists( "CurrentAmplitude" ) ) State( "CurrentAmplitude" );
	if( States->Exists( "NeedsUpdating" ) ) State( "NeedsUpdating" );
	if( States->Exists( "EnableTrigger" ) ) State( "EnableTrigger" );
	if( States->Exists( "BackgroundFeedbackValue" ) ) State( "BackgroundFeedbackValue" );
	if( States->Exists( "ProcessCompleted" ) ) State( "ProcessCompleted" );

	float InitialCurrentST = Parameter("InitialCurrentST");
	if( (InitialCurrentST < 0) | (InitialCurrentST > 5) )
	{
		bcierr << "For the ST H-reflex criteria, Initial Current must be between 0-5mA, currently set at " << InitialCurrentST << endl;
	}

}


void
CurrentControlCriteria::Initialize( const SignalProperties& Input, const SignalProperties& Output )
{

	nStimuli = Parameter("NumberOfStimuli");
	int BufferSize = nStimuli; // Buffer size is at least 1 current

	//Initialize Buffers
	mResponseBuffer = new RingBuffer( 1, BufferSize );
	mReferenceBuffer = new RingBuffer( 1, BufferSize );
	mAvgResponseBuffer = new RingBuffer( 1, 2 ); //These are the average of the last 2 values
	mAvgReferenceBuffer = new RingBuffer( 1, 2 );
	//Zero buffers
	ZeroSignal( mResponseBuffer );
	ZeroSignal( mReferenceBuffer );
	ZeroSignal( mAvgResponseBuffer );
	ZeroSignal( mAvgReferenceBuffer );

	//Set Delta currents
	ParamRef CurrentSettings = Parameter( "DeltaCurrent");
	mDeltaCurrent = (uInt16)(stod(CurrentSettings->Value())*1000); //Delta in uA
	mMinDeltaCurrent = (uInt16)(stod(CurrentSettings->LowRange())*1000);//minDelta in uA
	
	//Initialize global variables
	pTrialsCompleted = 0; // Previous Value of TrialsCompleted
	mBackgroundFeedbackValue = 0.0;
	mUpdateBackground = true;
	mCriteria = Parameter("Criteria");

	double maxCurrentStimulusTest = 15; //mA - Input or not?
	maxCurrentValue = (uInt16)( maxCurrentStimulusTest*1000); //Limit in uA
	
	mResponseFound = false;
	mResponseCurrent = 0;
	mEnabled = Parameter("EnableCurrentControl");
	mThreshold = Parameter("ThresholdMultiplier"); //Threshold Multiplier


}

void
CurrentControlCriteria::StartRun()
{
	State("ProcessCompleted") = 0;
}

void
CurrentControlCriteria::Process( const GenericSignal& Input, GenericSignal& Output )
{
	Output = Input; 

	bool AverageBuffersReady = false;
	
	//Set the background - This is when EnableTrigger is set to 1 and mUpdateBackground is 1
	//Idea is that when EnableTrigger is set we take the BackgroundValue (pre-stim) and use this as a threshold.
	//When we have the trap filter completed in capturing the window, i.e. TrialsCompleted incremented, we will set mUpdateBackground back to 1 to be reset for the next stim.
	if( (State("EnableTrigger") == 1) & (mUpdateBackground) )
	{
		mBackgroundFeedbackValue = State("BackgroundFeedbackValue")*2.85; // Multiplied by approx. 2*sqrt(2)
		mUpdateBackground = false;
	}

	int ProcessCompleted = State("ProcessCompleted");

	// Check if TrialsCompleted has increaseed
	if( (State("TrialsCompleted") - pTrialsCompleted > 0) & (ProcessCompleted==0) & (mEnabled==1)) 
	{
		mUpdateBackground = true;
		pTrialsCompleted = State("TrialsCompleted") ; //Update the previous (p) TrialsCompleted

		//Capture the Response and Reference Value
		unsigned int ResponseValue = State("ResponseFeedbackValue");
		unsigned int ReferenceValue = State("ReferenceFeedbackValue");

		//Update Buffers
		( *mResponseBuffer  )( 0, mResponseBuffer->mCursor  ) = ResponseValue;
		( *mReferenceBuffer )( 0, mReferenceBuffer->mCursor ) = ReferenceValue;

		//if we the buffers are full, i.e. mCursor == size(mResponseBuffer) then we take that average value and it to the average buffer
		if( mResponseBuffer->mCursor == nStimuli)
		{
			double mAvgRef = 0;
			double mAvgRes = 0;

			for(int i=0; i<mResponseBuffer->Elements(); i++)
			{
				mAvgRes += ( ( *mResponseBuffer   )( 0, i )/(double)nStimuli );
				mAvgRef += ( ( *mReferenceBuffer  )( 0, i )/(double)nStimuli );
			}

			( *mAvgReferenceBuffer )( 1, mAvgReferenceBuffer->mCursor ) = mAvgRef;
			( *mAvgResponseBuffer  )( 1, mAvgResponseBuffer->mCursor  ) = mAvgRes;

			if(mAvgResponseBuffer->mCursor == mAvgResponseBuffer->Elements()) //if there are 2 elements in the Average Buffers we are ready to process any criteria with this buffer
			{
				AverageBuffersReady = true;
			}

			mAvgResponseBuffer->Advance(); 
			mAvgReferenceBuffer->Advance();
		}

		//Capture Current Amplitude
		uInt16 CurrentCurrent = State("CurrentAmplitude");
		uInt16 NewCurrent = 0;

		// Now decide what criteria needs to be used
		if( AverageBuffersReady & ( (mCriteria==2) | (mCriteria==3) )  )
		{
			//So we have 2 values so we can now compute criteria

			//Check criteria depending on which is being used
			//NewCurrent = ComputeCriteria(mAvgReferenceBuffer,mAvgResponseBuffer);

			// Update CurrentAmplitude and NeedsUpdating 
			State("CurrentAmplitude") = NewCurrent;
			State("NeedsUpdating") = 1;
		}
		else if( mCriteria == 1) //Stimulus Test
		{
			//Compute criteria -> INPUTS:- Current, Delta, minDelta, Threshold
			bool ProcessDone = false; 
			NewCurrent = CurrentCurrent;

			//Will return True if delta has fallen below minDelta 
			float TH = mBackgroundFeedbackValue*mThreshold;
			ProcessDone = StimulusTestControl(ResponseValue, NewCurrent, mDeltaCurrent, mMinDeltaCurrent, TH, mResponseFound);
			
			if( mResponseFound ) //if a response was found at this current then let's update this
			{
				mResponseCurrent = CurrentCurrent;
			}

			//if the NewCurrent is too large then we stop
			if( NewCurrent > maxCurrentValue)
			{
				State("CurrentAmplitude") = mResponseCurrent;
				State("ProcessCompleted") = 1;
				State("NeedsUpdating") = 1;	
				bciout << "Current exceeds maximum limit for Stimulus Test at " << double(maxCurrentValue)/1000 << "mA" << endl;
			}
			else
			{
	
				if( ProcessDone )
				{
					State("CurrentAmplitude") = mResponseCurrent;
					bciout << "Current found for Stimulus Test at " << double(mResponseCurrent)/1000 << "mA" << endl;
				}
				else
				{
					State("CurrentAmplitude") = NewCurrent;
					bciout << "new Current is " << double(NewCurrent)/1000 << "mA" << endl;
				}
				
				State("NeedsUpdating") = (int)!ProcessDone;
				State("ProcessCompleted") = (int)ProcessDone;
			}	
			
		}
		else //Criteria == 4 (Control/Training Trial)
		{
		}

	mResponseBuffer->Advance();
	mReferenceBuffer->Advance();


	} //End if TrialsCompleted Changed

}


void
CurrentControlCriteria::StopRun()
{
	State("CurrentAmplitude") = mResponseCurrent;
}

void
CurrentControlCriteria::Halt()
{


}

bool		 
CurrentControlCriteria::StimulusTestControl(unsigned int HAmplitude, uInt16 & CurrentAmplitude, uInt16 & Delta, uInt16 minDelta, double Threshold, bool & ResponseFound)
{
	//HAmplitude - Raw value in MicroVolts
	//CurrentAmplitude - Value from CurrentAmplitude state (16bit representation of 0-5V
	//Delta - CurrentSteps to Start with (this is in mA, not 16bit representation)...
	//minDelta - minimum Delta before we stop looking
	//Threshold - value that HAmplitude needs to be greater than to be considered 
	//Return will be false if we continue, true to stop the process.
	//bciout << "H amplitude = " << HAmplitude << endl;
	//bciout << "Threshold = " << Threshold << endl;
	//Check if there is a response
	if(double(HAmplitude) > (Threshold))
	{
		
		//If yes, great! 
		ResponseFound = true;
		
		//If the CurrentDelta is les than or equal to the minimum then we are done
		if(Delta <= minDelta)
		{
			return true;
		}
		else
		{
			//We still need to narrow down so we go down half of current delta
			Delta = (uInt16)::Round((double)Delta/2);
			CurrentAmplitude = CurrentAmplitude - Delta;	
			return false;
		}
	}
	else
	{
		//Oh no!
		//Well if there was one before (i.e. we have gone down a delta), and delta < minDelta then we need to increase current amplitude and then finish
		if(Delta <= minDelta)
		{
			CurrentAmplitude = CurrentAmplitude + Delta; //Restore previous currentvalue
			ResponseFound = true;
			return true;
		}
		else
		{
			//We still need to narrow down so we go up half of current delta
			if( ResponseFound )
			{
				Delta = (uInt16)::Round((double)Delta/2);
				CurrentAmplitude = CurrentAmplitude + Delta;
			}
			else
			{
				CurrentAmplitude = CurrentAmplitude + Delta;
			}

				
			return false;
		}

	}

}


void
CurrentControlCriteria::ZeroSignal( GenericSignal * signal )
{
  for( int ch = 0; ch < signal->Channels(); ch++ )
    for( int el = 0; el < signal->Elements(); el++ )
      ( *signal )( ch, el )  = 0.0;
}
