/////////////////////////////////////////////////////////////////////////////
// $Id: NIDAQFilterAnalogStim.cpp 4648 2013-11-21 00:09:31Z AEftekhar $
// Author: Jeremy Hill & justin.renga@gmail.com                            //
// Description: An output filter for National Instruments Data Acquisition //
//              Boards                                                     //
//                                                                         //
// $BEGIN_BCI2000_LICENSE$
//
// This file is part of BCI2000, a platform for real-time bio-signal research.
// [ Copyright (C) 2000-2012: BCI2000 team and many external contributors ]
//
// BCI2000 is free software: you can redistribute it and/or modify it under the
// terms of the GNU General Public License as published by the Free Software
// Foundation, either version 3 of the License, or (at your option) any later
// version.
//
// BCI2000 is distributed in the hope that it will be useful, but
//                         WITHOUT ANY WARRANTY
// - without even the implied warranty of MERCHANTABILITY or FITNESS FOR
// A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License along with
// this program.  If not, see <http://www.gnu.org/licenses/>.
//
// $END_BCI2000_LICENSE$
/////////////////////////////////////////////////////////////////////////////
//#include "PCHIncludes.h"
#pragma hdrstop
#include "NIDAQFilterAO.h"
#include "BCIEvent.h"
#include "StringUtils.h"
#include <sstream>
using namespace std;

RegisterFilter( NIDAQFilterAO, 2.C );

NIDAQFilterAO::NIDAQFilterAO()
{
}

NIDAQFilterAO::~NIDAQFilterAO()
{
	Halt();
}


void
	NIDAQFilterAO::Publish()
{
	BEGIN_PARAMETER_DEFINITIONS

		"Filtering:NIDAQFilterAO int DigitalOuput= 1 1 0 1 // Enable Digital Output? (boolean)",           
		"Filtering:NIDAQFilterAO int AnalogOutput= 1 1 0 1 // Enable Analog Output? (boolean)", 
		"Filtering:NIDAQFilterAO matrix FilterExpressions= "
		" 2 { Output%20Type Device%20Name Port/Line	Expression/Current}   "
		"        Digital       Dev2       port0/Line7 EnableTrigger       "
		"        Analog        Dev2           ao0    CurrentAmplitude     "
		" % % % // specification for Analog and Digital Output",
		"Stimulation:NIDAQFilterAO int Biphasic=   1  1  1  2 // Options are 1=Yes 2=No(enumeration)",
		"Stimulation:NIDAQFilterAO int StimulationType=   1  1  1  6 // Options are 1=square 2=sine 3=linear_rising 4=linear_down 5=exp_rising 6=exp_down(enumeration)",
		"Stimulation:NIDAQFilterAO float PulseWidth= 0.5ms 0.5ms % % // PulseWidth of the Analog Stimulii in \"ms\"",
		"Stimulation:NIDAQFilterAO float InterphasicDelay= 0.1ms 0.1ms % % // Interphasic Delay of the Analog Stimulii in \"ms\"",
		"Stimulation:NIDAQFilterAO float InitialCurrent= 0 1 % % // Initial Current to Use for Stimulation \"mA\"",
		"Stimulation:NIDAQFilterAO int AORange= 5 5 2 10 // Output range for Analog Output in Volts (default 5V)",
		END_PARAMETER_DEFINITIONS
		

		BEGIN_STATE_DEFINITIONS

		"CurrentAmplitude   16 0 0 0",  // Value represented as uA so we have 0-65535uA (or 65.535mA max)
		"NeedsUpdating   1 0 0 0",
		END_STATE_DEFINITIONS

}

int
	NIDAQFilterAO::ParseMatrix(
	std::string			& AnalogDeviceName,
	std::string		    & DigitalDeviceName,
	std::string			& AnalogPortSpec,
	std::string			& DigitalPortSpec,
	bool				& AnalogUse,
	bool				& DigitalUse,
	std::string			& AnalogState,
	std::string			& DigitalState,
	std::string			& aDeviceName
	) const
{
	string paramName = "FilterExpressions";
	ParamRef matrix = Parameter( paramName );
	vector<string>     lDevices;
	bool AnalogFound=0;
	bool DigitalFound=0;

	DigitalUse = Parameter( "DigitalOuput" );
	AnalogUse = Parameter( "AnalogOutput" );

	lDevices = CollectDeviceNames(); // Preflight will check if any devices present

	int nOutputs = (int)(DigitalUse) + (int)(AnalogUse);

	if( matrix->NumRows() < nOutputs)
		bcierr << paramName << " parameter must have at least "<< nOutputs <<" row(s)" << endl;
	if( matrix->NumColumns() != 4 )
		bcierr << paramName << " parameter must have 4 columns" << endl;

	for( int row = 0; row < matrix->NumRows(); row++ )
	{
		int col = -1;

		string channelType = StringUtils::Strip( matrix( row, ++col ));

		if(StringUtils::ToLower(channelType)=="analog") 
		{
			AnalogFound = 1;

			if(AnalogUse)
			{

				string deviceName = StringUtils::Strip( matrix( row, ++col ));
				aDeviceName = deviceName;
				if( !find( deviceName, lDevices ) )  // is the device connected to the computer?
					bcierr << deviceName << " is not connected to the computer. Please check connections and try again" << endl;


				AnalogDeviceName = deviceName ;
				string PortSpec = StringUtils::ToLower(StringUtils::Strip( matrix( row, ++col )));

				char AOChannels[64];
				vector<string> AOChannelsList;
				ReportError ( DAQmxGetDevAOPhysicalChans(deviceName.c_str(),AOChannels, 64 ) ) ;
				Tokenize( AOChannels, AOChannelsList, ',', true, true );
				if( !find( deviceName+"/"+PortSpec , AOChannelsList ) )
				{
					bcierr << "Specified Analog Output Channel" << PortSpec << " cannot be found on this device" << endl;
				}

				AnalogPortSpec = deviceName+"/"+PortSpec;

				AnalogState = StringUtils::Strip( matrix( row, ++col ));
				if( States->Exists( AnalogState ) ) State( AnalogState );
			}
		}
		else if(StringUtils::ToLower(channelType)=="digital") 
		{
			DigitalFound = 1;

			if( DigitalUse)
			{
				string deviceName = StringUtils::Strip( matrix( row, ++col ));
				if( !find( deviceName, lDevices ) )  // is the device connected to the computer?
					bcierr << deviceName << " is not connected to the computer. Please check connections and try again" << endl;


				DigitalDeviceName = deviceName ;
				string PortSpec = StringUtils::ToLower(StringUtils::Strip( matrix( row, ++col )));

				char DOChannels[1280];
				vector<string> DOChannelsList;
				ReportError ( DAQmxGetDevDOLines(deviceName.c_str(),DOChannels, 1280 ) ) ;
				Tokenize( DOChannels, DOChannelsList, ',', true, true );
				if( !find( deviceName+"/"+PortSpec , DOChannelsList ) )
				{
					bcierr << "Specified Analog Output Channel" << PortSpec << " cannot be found on this device" << endl;
				}

				DigitalPortSpec = deviceName+"/"+PortSpec;

				DigitalState = StringUtils::Strip( matrix( row, ++col ));
				if( States->Exists( DigitalState ) ) State( DigitalState );
			}
		}
		else
		{
			bcierr << "could not interpret " << channelType << " as a NIDAQ output type. Please use Analog or Digital" << endl;
		}

	}

	if (AnalogUse & !AnalogFound) 
	{bcierr << "No Analog settings set in the FilterExpressions parameter" << endl;}
	if (DigitalUse & !DigitalFound) 
	{bcierr << "No Digital settings set in the FilterExpressions parameter" << endl;}

	return nOutputs;
}


void
	NIDAQFilterAO::Preflight( const SignalProperties& Input, SignalProperties& Output ) const
{
	Output = Input; // this simply passes information through about SampleBlock dimensions, etc....
	std::string		AnalogDeviceName;
	std::string		DigitalDeviceName;
	std::string		AnalogPortSpec;
	std::string		DigitalPortSpec;
	bool			AnalogUse;
	bool			DigitalUse;
	std::string		AnalogState;
	std::string		DigitalState;
	std::string		DeviceName;

	if( States->Exists( "NeedsUpdating" ) ) State( "NeedsUpdating" );
	if( States->Exists( "CurrentAmplitude" ) ) State( "CurrentAmplitude" );

	//TODO: NEED TO DECIDE ON HOW TO MANAGE THE PFI0 INPUT - i.e. IF IT DOESN'T HAVE ONE
	ParseMatrix( AnalogDeviceName, DigitalDeviceName, AnalogPortSpec, DigitalPortSpec, AnalogUse, DigitalUse, AnalogState, DigitalState,DeviceName);
	//ParseMatrix will have checked the DeviceNames used and connected, the AO and AI Ports and checked if there are states
	bool iDS5 = Parameter("EnableDS5ControlFilter");
	bool iDS8 = Parameter("EnableDS8ControlFilter");
	float Current = Parameter("InitialCurrent");

	

	//IF THERE IS A NEED FOR AN ANALOG OR DIGITAL TASK TRY CREATING TASKS
	if(DigitalUse)
	{
		TaskHandle task;
		if( ReportError( DAQmxCreateTask( "Digital_Output", &task ) ) < 0 )
			bcierr << "Unable to create task \"Digital_Output\" " << endl;
		if( ReportError( DAQmxCreateDOChan( task, DigitalPortSpec.c_str(), "", DAQmx_Val_ChanForAllLines ) ) < 0 )
			bcierr << "Unable to create channel operating on the following lines: " << DigitalPortSpec.c_str() << endl;
		if( ReportError( DAQmxClearTask( task ) ) < 0 )
			bcierr << "Failed to clear task \"Digital_Output\" " << endl;
	}

	if(AnalogUse)
	{
		//CHECK AOUT RANGE -> How? Does BCI2000 automatically check this value?
		float localMin = 0.0f;
		float localMax = 0.0f;
		ParamRef AORange = Parameter( "AORange" );

		localMin = -1*(float)MeasurementUnits::ValueIn( "V", AORange( 0 ) );
		localMax = (float)MeasurementUnits::ValueIn( "V", AORange( 0 ) );

		TaskHandle task;

		if( ReportError( DAQmxCreateTask( "Analog_Output", &task ) ) < 0 )
			bcierr << "Unable to create task \"Analog_Output\" " << endl;
		if( ReportError( DAQmxCreateAOVoltageChan( task, AnalogPortSpec.c_str(), "", localMin, localMax, DAQmx_Val_Volts, NULL ) ) < 0 )
			bcierr << "Failed to create channel operating on the following lines: " << AnalogPortSpec.c_str() << endl;

		//NOT NEEDED FOR DS8 = THE DS8 WILL USE SINGLE SAMPLE UPDATES SO DON'T NEED TO SET UP RETRIGGERING ETC...
		if (iDS5)
		{
			//CHECK STIMULATION TYPE
			//CHECK PULSEWIDTH
			double PulseWidth = Parameter( "PulseWidth" ).InSeconds(); //***
			double InterphasicDelay = Parameter( "InterphasicDelay" ).InSeconds(); //***
			bool Biphasic = (bool)Parameter( "Biphasic" );
			int StimPhaseNSamples[3] = {0,0,0};

			if( (PulseWidth < 0.0003) && (PulseWidth > 0.002)) //***
			{
				bciwarn << "Warning: Pulse Width is " << PulseWidth << ", which is outside the 0.3-2ms used for H-reflex conditioning" << endl;
			}
			//CHECK RISETIME
			
			double SampleRate = 0; //***
			float64 allowedSampleRate;//***
			DAQmxGetDevAOMaxRate(DeviceName.c_str(),&allowedSampleRate);//***
			if (allowedSampleRate > 100000)
			{SampleRate = 100000;}
			else
				{SampleRate = allowedSampleRate;
				bciwarn << "Sample Rate," << SampleRate << ", for AO has been adjusted as it was set higher than the device limit, " << allowedSampleRate << endl;
			}

			int StimType = Parameter("StimulationType"); //***

			int NumberOfSamples = 1;

			//Can't seem to call my function here, thanks BCI2000...
			int N1 = (int)(PulseWidth*SampleRate) + 1; int N2 = 0; int N3 = 0;
			if (Biphasic)
			{
				if (InterphasicDelay != 0)
					N2 = (int)(InterphasicDelay*SampleRate/1000) + 1;
				N3 = N1;
				//output[0] = N1; output[1] = N2; output[2] = N3;
				NumberOfSamples = N1 + N2 + N3;
			}
			else
			{
				//output[0] = N1; output[1] = N2; output[2] = N3;
				NumberOfSamples = N1;
			}

			if(NumberOfSamples - (unsigned int)(NumberOfSamples) > 0.0) //***
			{
				double ActualNumberOfSamplesMS = 1000*(unsigned int)(NumberOfSamples)/SampleRate;
				bcierr << "Value for PulseWidth, " << Parameter( "PulseWidth" ).InMilliseconds() << "ms, with a Sampling Rate of " << SampleRate << ", yields a non-integer number of sample points. Stimulation will be rounded to " << ActualNumberOfSamplesMS << "ms" << endl;
			}
			

			if(ReportError (DAQmxCfgSampClkTiming(task,"",SampleRate,DAQmx_Val_Rising,DAQmx_Val_FiniteSamps,(unsigned int)(NumberOfSamples))) < 0) //***
				bcierr << "Unable set Sampling Clock for \"Analog_Output\" " << endl; //***
			string PFIport = AnalogDeviceName + "/PFI0"; //***
			if(ReportError (DAQmxCfgDigEdgeStartTrig(task,PFIport.c_str(),DAQmx_Val_Rising))<0) //***
				bcierr << "Unable to set Digital Edge Trigger for Analog Output" << endl; 
			if((DAQmxSetStartTrigRetriggerable(task,1))<0) //SOME DEVICES DO NOT SUPPORT RE-TRIGGERABLE //***
				bciwarn << "Unable set Analog Output to Retriggerable, not supported by you NI device. We will set this to restablish Digital Edge Trigger each time Stimulus is to be updated." << endl;
		
		}
		else
		{
			double NumberOfSamples = 1;
		}

		if( Current < 0) 
			bcierr << "Initial Current should be greater than or equal to 0mA" << endl;
		if( Current > 50) 
			bcierr << "Initial Current should be less than 50mA" << endl;
		
		if( ReportError( DAQmxClearTask( task ) ) < 0 )
			bcierr << "Failed to clear task \"Analog_Output\" " << endl;

		if(( (int)localMax != 1) && ( (int)localMax != 2.5) && ( (int)localMax != 5) && ( (int)localMax != 10))
		bciwarn << "Analog Output Range is set to " << localMax << " and not Digitimer DS5 ranges of +/-1, 2.5, 5 or 10" << endl;
	}
	
}


void
	NIDAQFilterAO::Initialize( const SignalProperties& Input, const SignalProperties& Output )
{


	ParseMatrix( mAnalogDeviceName, mDigitalDeviceName, mAnalogPortSpec, mDigitalPortSpec, mAnalogUse, mDigitalUse, mAnalogState, mDigitalState,mAnalogDevice);


	//IF DIGITAL CREATE TASKS
	//IF ANALOG CREATE TASKS

	//EXTRACT DETAILS FROM FILTERMATRIX (ASSUME IT HAS BEEN CHECKED)

	//Should have already been checked in preflight to make sure 
	mDS5 = Parameter("EnableDS5ControlFilter");
	mDS8 = Parameter("EnableDS8ControlFilter");

	if (mDS5)
	{	
		mMaxValue = 50000;
	}
	else if (mDS8)
	{
			mMaxValue = 500000;
	}

	initialCurrent = (uInt16)(Parameter("InitialCurrent")*1000);
	bciout << "initial current: " << std::to_string(initialCurrent) << std::endl;

	if( mDigitalUse )
	{
		if( ReportError( DAQmxCreateTask( "Digital_Output", &mDigitalTaskHandle ) ) < 0 )
			bcierr << "Unable to create task \"Digital_Output\" " << endl;
		//mDigitalPortSpec.c_str()
		if( ReportError( DAQmxCreateDOChan( mDigitalTaskHandle,mDigitalPortSpec.c_str(), "", DAQmx_Val_ChanPerLine ) ) < 0 )
			bcierr << "Failed to create channel operating on the following lines: " << mDigitalPortSpec.c_str() << endl;
	}

	if( mAnalogUse )
	{
		float localMin = 0.0f;
		float localMax = 0.0f;
		mAORange = Parameter( "AORange" ); 
		localMin = -1*(float)(mAORange);
		localMax = (float)(mAORange);

		mStimType = Parameter("StimulationType");
		//1=square 2=sine 3=linear_rising 4=linear_down 5=exp_rising 6=exp_down

		bciout << "Stim Type: " << mStimType << endl;
		mBiphasic = (bool)Parameter("Biphasic");
		mRestartSetTrigger = false;

		if( ReportError( DAQmxCreateTask( "Analog_Output", &mAnalogTaskHandle ) ) < 0 )
			bcierr << "Unable to create task \"Analog_Output\" " << endl;
		if( ReportError( DAQmxCreateAOVoltageChan( mAnalogTaskHandle, mAnalogPortSpec.c_str(), "", localMin, localMax, DAQmx_Val_Volts, NULL ) ) < 0 )
			bcierr << "Failed to create channel operating on the following lines: " << mAnalogPortSpec.c_str() << endl;

		if (mDS5)
		{

			mPulseWidth = Parameter( "PulseWidth" ).InSeconds();//***
			mInterphasicDelay = Parameter( "InterphasicDelay" ).InSeconds();//***
						
			float64 allowedSampleRate; //***
			DAQmxGetDevAOMaxRate(mAnalogDevice.c_str(),&allowedSampleRate); //***
		
			mSampleRate = 0;//***
			
			if (allowedSampleRate > 100000)
				{
					mSampleRate = 100000;
				}
			else
				{
					mSampleRate = allowedSampleRate;
				bciwarn << "Sample Rate," << mSampleRate << ", for AO has been adjusted as it was set higher than the device limit, " << allowedSampleRate << endl;
				}
			
			bciout << "SampleRate set to: " << mSampleRate << endl;

			//mNumberOfSamples = (PulseWidth*SampleRate + 1) ;//*** NUMBER OF SAMPLES=1
			mNumberOfSamples = (double)NoSamplesCalc(mStimPhaseNSamples, mSampleRate, mPulseWidth*1000, mInterphasicDelay*1000, mBiphasic, 1);
			mNumberOfSamples += 1;

			bciout << "NumberofSamples set to: " << mNumberOfSamples <<  endl;

			//FOR THE DS8 WE DON'T NEED TO SET THESE, WILL JUST SET THE ANALOG OUTPUT VALUE
			if(ReportError (DAQmxCfgSampClkTiming(mAnalogTaskHandle,"",mSampleRate,DAQmx_Val_Rising,DAQmx_Val_FiniteSamps,(uInt64)mNumberOfSamples)) < 0)//***
				bcierr << "Unable set Sampling Clock for \"Analog_Output\" " << endl;

			string PFIport = "/"+ mAnalogDeviceName + "/PFI0";//***
			if(ReportError (DAQmxCfgDigEdgeStartTrig(mAnalogTaskHandle,PFIport.c_str(),DAQmx_Val_Rising))<0)//***
				bcierr << "Unable to set Digital Edge Trigger for Analog Output" << endl;
			if(DAQmxSetStartTrigRetriggerable(mAnalogTaskHandle,1)<0)//***
				mRestartSetTrigger = true; //***

			
			mAnalogBuffer =  new float64[(unsigned int)(mNumberOfSamples)]; //Add a zero otherwise signal will stay at previous value
			mTemplateBuffer =  new float64[(unsigned int)(mNumberOfSamples)]; //Add a zero otherwise signal will stay at previous value
			float64 val = Parameter("InitialCurrent")*1000; //Value in uA
			float64 Amplitude = mAORange*(val/mMaxValue); //TODO: update 50000 when we have DS5 code

			//writeAnalogBuffer(Amplitude,mNumberOfSamples, mAnalogBuffer,mStimType,mSteps);
			//ConstructStimWaveform(float64* &StimBuffer,std::string StimTypeN,std::string StimTypeP, double SamplingFrequency, double PulseWidth, double InterphasicDelay, bool Biphasic,int R, double Amp, int NumberSamples, int* StimPhaseNSamples)
			//Note currently defaults to square wave second phase.
			ConstructStimWaveform(mTemplateBuffer,mStimType,mStimType,mSampleRate,mPulseWidth*1000,mInterphasicDelay*1000,mBiphasic,1,1,mNumberOfSamples,mStimPhaseNSamples);
			
			for (int i=0;i<mNumberOfSamples-1;i++)
			{
				mAnalogBuffer[i] = mTemplateBuffer[i]*Amplitude;	
			}

			mAnalogBuffer[(int)mNumberOfSamples-1] = 0;

			/*for (int i=0;i<mNumberOfSamples-1;i++)
			{
				bciout << "Sample " << i << ": " << mAnalogBuffer[i];
			}*/

		}
		else
		{
			mNumberOfSamples = 1;
		}
	
	}



}



void
	NIDAQFilterAO::Process( const GenericSignal& Input, GenericSignal& Output )
{

	Output = Input; // Pass the signal through unmodified.
	//OUTPUT DIGITAL VALUES
	//UPDATE ANALOG ONES IF NECESSARY

	int32 lWritten;

	bool Update = State("NeedsUpdating");

	if (mAnalogUse & mRestartSetTrigger) //Not the most efficient way but this will restart the trigger process for analog output if it needs set
	{	

		if( mAnalogTaskHandle && ReportError( DAQmxStopTask( mAnalogTaskHandle ) ) < 0 )
			bcierr << "Failed to stop task \"Analog_Output\" " << endl;

		string PFIport = "/"+ mAnalogDeviceName + "/PFI0";
		if(ReportError (DAQmxCfgDigEdgeStartTrig(mAnalogTaskHandle,PFIport.c_str(),DAQmx_Val_Rising))<0)
			bcierr << "Unable to set Digital Edge Trigger for Analog Output" << endl;

		if( mAnalogTaskHandle && ReportError( DAQmxStartTask( mAnalogTaskHandle ) ) < 0 )
			bcierr << "Failed to start task \"Analog_Output\" " << endl;

	}

	if( mAnalogUse ) 
	{

		if (Update | mRestartSetTrigger)
		{
			// STOP TASK 
			if( mAnalogTaskHandle && ReportError( DAQmxStopTask( mAnalogTaskHandle ) ) < 0 )
				bcierr << "Failed to stop task \"Analog_Output\" " << endl;
		}

		if (Update)
		{
			//GET CURRENT AMPLITUDE TO USE
			uInt16 val = State("CurrentAmplitude");
			float64 Amplitude = mAORange*(((float64)val)/mMaxValue);
			bciout << "Current set to " << Amplitude << endl;

			if (mDS5)
			{
				//writeAnalogBuffer(Amplitude,mNumberOfSamples,mAnalogBuffer,mStimType,mSteps);
				//REFILL mAnalogBuffer
				for (int i=0;i<mNumberOfSamples-1;i++)
				{
					mAnalogBuffer[i] = mTemplateBuffer[i]*Amplitude;
				}
				mAnalogBuffer[(int)mNumberOfSamples-1] = 0;
		
				//RE-WRITE //*** THIS WILL JUST WRITE ONE VALUE, DON'T THINK WE NEED TO USE THE BUFFER BUT EASIER TO NOT CHANGE

				if( ReportError( DAQmxWriteAnalogF64( mAnalogTaskHandle, mNumberOfSamples, 0, 1, DAQmx_Val_GroupByChannel, mAnalogBuffer, NULL, NULL ) ) < 0 )
				{
					bcierr << "Failed to write to task \"Analog_Output\"" << endl;
					return;
				}
			
			}

			State("NeedsUpdating") = false;
		}

		if (Update | mRestartSetTrigger)
		{
			//RESTART TASK
			if( mAnalogTaskHandle && ReportError( DAQmxStartTask( mAnalogTaskHandle ) ) < 0 )
				bcierr << "Failed to start task \"Analog_Output\" " << endl;
		}


	}

	if( mDigitalUse )
	{

		float64 floatVal = (float64)State(mDigitalState);
		mDigitalBuffer[0] = (uInt8)floatVal;

		if( ReportError( DAQmxWriteDigitalLines( mDigitalTaskHandle, 1, false, 1.0, DAQmx_Val_GroupByScanNumber, mDigitalBuffer, &lWritten, NULL ) ) < 0 )
		{
			bcierr << "Failed to write to task \"Digital_Output\"" << endl;
			return;
		}

	}





}


void
	NIDAQFilterAO::StartRun()
{

	if(mDigitalUse)
	{
		if( mDigitalTaskHandle && ReportError( DAQmxStartTask( mDigitalTaskHandle ) ) < 0 )
			bcierr << "Failed to start task \"Digital_Output\" " << endl;
	}
	if( mAnalogUse)
	{
		if (mDS5)
		{
			if( ReportError( DAQmxWriteAnalogF64( mAnalogTaskHandle, mNumberOfSamples, 0, 1, DAQmx_Val_GroupByChannel, mAnalogBuffer, NULL, NULL ) ) < 0 )
			{
				bcierr << "Failed to write to task \"Analog_Output\"" << endl;
				return;
			}
		}

			
		if( mAnalogTaskHandle && ReportError( DAQmxStartTask( mAnalogTaskHandle ) ) < 0 )
			bcierr << "Failed to start task \"Analog_Output\" " << endl;
	}

	State("CurrentAmplitude") = initialCurrent;
}
void
	NIDAQFilterAO::StopRun()
{
	if( mAnalogTaskHandle )
	{
		if( ReportError( DAQmxStopTask( mAnalogTaskHandle ) ) < 0 )
			bcierr << "Failed to stop task \"Analog_Output\" " << endl;
	}
	if( mDigitalTaskHandle )
	{
		if( ReportError( DAQmxStopTask( mDigitalTaskHandle ) ) < 0 )
			bcierr << "Failed to stop task \"Digital_Output\" " << endl;
	}
}

void
	NIDAQFilterAO::Halt()
{
	if( mAnalogTaskHandle )
		DAQmxClearTask( mAnalogTaskHandle );
	if( mDigitalTaskHandle )
		DAQmxClearTask( mDigitalTaskHandle );
	mAnalogTaskHandle = mDigitalTaskHandle = NULL;
}


// Report any NIDAQmx Errors that may occur //
int
	NIDAQFilterAO::ReportError( int errCode ) const
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

void
	NIDAQFilterAO::Tokenize( std::string whole, std::vector<std::string>& parts, char delim, bool stripParts, bool discardEmpties )
{
	stringstream ss( whole );
	string part;
	while( getline( ss, part, delim ) )
	{
		if( stripParts ) part = StringUtils::Strip( part );
		if( part.size() || !discardEmpties ) parts.push_back( part );
	}
}


// Collect the device names (display them in operator log as well) //
vector<string>
	NIDAQFilterAO::CollectDeviceNames() const
{
	char localDevices[ 32 ];
	vector<string>  localDeviceList;
	if( ReportError( DAQmxGetSysDevNames( localDevices, 32 ) ) < 0 )
	{
		bcierr << "Unable to detect any devices. Please make sure devices are properly connected to system and try again." << endl;
		return localDeviceList;
	}
	Tokenize( localDevices, localDeviceList, ',', true, true );
	for( std::vector<std::string>::iterator i = localDeviceList.begin(); i != localDeviceList.end(); ++i )
	{
		char localInformation[ 32 ];
		string localToken = *i;
		DAQmxGetDevProductType( localToken.c_str(), localInformation, 32 );
		bcidbg( 0 ) << localToken << " Product Type " << localInformation << endl;
	}
	return localDeviceList;
}

bool
	NIDAQFilterAO::find( string deviceName, vector<string> names )
{
	for( vector<string>::iterator itr = names.begin(); itr != names.end(); itr++ )
		if( ( *itr ) == deviceName )  // if the devicename was found inside of names, return true!
			return true;
	return false;  // the end of the loop has been reached : the name wasn't found
}

void
NIDAQFilterAO::writeAnalogBuffer(double Val, double NumberOfSamples, float64* &AnalogBuffer, int StimType, int Steps)
{

	if( StimType == 1)
	{
		
		for(int i=0;i<Steps-1;i++)
		{
			AnalogBuffer[i] = (Val*i) / Steps;
		}

		int N = NumberOfSamples - Steps;

		for(int i=Steps-1;i<N;i++)
		{
			AnalogBuffer[ i ] = Val; 
		}

		for(int i=N;i<NumberOfSamples-1;i++)
		{
			AnalogBuffer[i] = (Val*(NumberOfSamples-i-1)) / Steps;
		}

		AnalogBuffer[ (unsigned int)NumberOfSamples-1 ] = 0;
	}
	else
	{


		for(int i=0;i<Steps-1;i++)
		{
			AnalogBuffer[i] = (Val*(i+1)) / Steps;
		}

		int N = (NumberOfSamples/2) - Steps;

		for(int i=Steps-1;i<N;i++)
		{
			AnalogBuffer[ i ] = Val; 
		}

		for(int i=N;i<(NumberOfSamples/2)-1;i++)
		{
			AnalogBuffer[i] = (Val*((NumberOfSamples/2)-i-1)) / Steps;
		}

		AnalogBuffer[ (unsigned int)(NumberOfSamples/2)-1 ] = 0;

		for(int i =(NumberOfSamples/2); i<NumberOfSamples;i++ )
		{
			AnalogBuffer[i] = -1*AnalogBuffer[i-(int)(NumberOfSamples/2)];
		}


	}
}

//Stimulation Construction Code from here!

int 
NIDAQFilterAO::NoSamplesCalc(int* output, double SamplingFrequency, double PulseWidth, double InterphasicDelay, bool Biphasic, int R)
{
	int N1 = (int)(PulseWidth*SamplingFrequency/1000) + 1;
	int N2 = 0;
	int N3 = 0;
	if (Biphasic)
	{
		if (InterphasicDelay != 0)
			N2 = (int)(InterphasicDelay*SamplingFrequency/1000) + 1;
		//R is a ratio, so if 1, the amplitude magnitude (x-1) and duration will be the same; 
		N3 = N1*R;
		output[0] = N1; output[1] = N2; output[2] = N3;
		return N1 + N2 + N3;
	}
	else
	{
		output[0] = N1; output[1] = N2; output[2] = N3;
		return N1;
	}

	
}

void NIDAQFilterAO::WaveFormGenerate_phase13(int StimType, double NumberOfSamples, float64* &StimBuffer,float Amp,int offset, float PulseWidth, double SamplingFrequency)
{


	switch(StimType) {
		case 1:  //square
			for(int i=offset;i<NumberOfSamples;i++)
			{
				StimBuffer[ i ] = Amp; 
			}
			break;
		case 2: //sine
			for(int i=offset;i<NumberOfSamples;i++)
			{
				StimBuffer[ i ] = Amp*sin(3.142*(1000/PulseWidth)*(i-offset)*(1/SamplingFrequency)); 
			}
			break;
		case 3: //linear increase
			for(int i=offset;i<NumberOfSamples;i++)
			{
				StimBuffer[ i ] = Amp*(i-offset)/NumberOfSamples; 
			}
			break;
		case 4: //linear decreas
			for(int i=offset;i<NumberOfSamples;i++)
			{
				StimBuffer[ i ] = Amp*(1 - ((i-offset)/NumberOfSamples)); 
			}
			break;
		case 5: //exponential increase
			for(int i=offset;i<NumberOfSamples;i++)
			{
				StimBuffer[ i ] = Amp*exp( -5*(1- ((i-offset)/NumberOfSamples)) ); 
			}
			break;
		case 6: //exponential decrease
			for(int i=offset;i<NumberOfSamples;i++)
			{
				StimBuffer[ i ] = Amp*exp( -5*((i-offset)/NumberOfSamples) ); 
			}
			break;

	}

}
void NIDAQFilterAO::WaveFormGenerate_phase2(double NumberOfSamples, float64* &StimBuffer,int offset)
{
	for(int i=offset;i<NumberOfSamples;i++)
			{
				StimBuffer[ i ] = 0; 
			}
}

void NIDAQFilterAO::ConstructStimWaveform(float64* &StimBuffer,int StimTypeN,int StimTypeP, double SamplingFrequency, double PulseWidth, double InterphasicDelay, bool Biphasic,int R, double Amp, int NumberSamples, int* StimPhaseNSamples)
{
	//Initialize Variable
	
	//first phase
	WaveFormGenerate_phase13(StimTypeN,StimPhaseNSamples[0],StimBuffer,Amp,0,PulseWidth,SamplingFrequency);
	//second phase
	WaveFormGenerate_phase2(StimPhaseNSamples[0]+StimPhaseNSamples[1],StimBuffer,StimPhaseNSamples[0]);
	//third phase
	WaveFormGenerate_phase13(StimTypeP,StimPhaseNSamples[0]+StimPhaseNSamples[1]+StimPhaseNSamples[2],StimBuffer,-1/(float)R,StimPhaseNSamples[0]+StimPhaseNSamples[1],PulseWidth,SamplingFrequency);

}