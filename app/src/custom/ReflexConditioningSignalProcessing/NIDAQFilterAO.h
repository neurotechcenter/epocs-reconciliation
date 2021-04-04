////////////////////////////////////////////////////////////////////////////////
// Authors: 
// Description: NIDAQFilterAO header
////////////////////////////////////////////////////////////////////////////////

#ifndef NIDAQ_FILTERAO_H  // makes sure this header is not included more than once
#define NIDAQ_FILTERAO_H

#include "GenericFilter.h"
#include "OSThread.h"
#include "NIDAQmx.imports.h"
#include "Expression.h"
#include <vector>
#include <string>
#include <map>
#include <fstream>
#include <algorithm>

class NIDAQFilterAO : public GenericFilter
{
public:
	NIDAQFilterAO();
	virtual ~NIDAQFilterAO();
	virtual void Publish();
	virtual void Halt() ;
	virtual void Preflight( const SignalProperties& Input, SignalProperties& Output ) const;
	virtual void Initialize( const SignalProperties& Input, const SignalProperties& Output );
	virtual void StartRun() ;
	virtual void Process( const GenericSignal& Input, GenericSignal& Output );
	virtual void StopRun() ;
private:

	// Member Functions [Private] //
	int    ReportError(int errCode) const;                     //  reports any NIDAQ error that may be called
	std::vector<std::string> CollectDeviceNames() const;
	static void Tokenize( std::string whole, std::vector<std::string>& parts, char delim, bool stripParts = true, bool discardEmpties = true );
	static bool find(std::string, std::vector<std::string>);   // determines if the specified device is connected to the computer
	// Use this space to declare any Test-specific methods and member variables you'll need
	TaskHandle        mDigitalTaskHandle;
	TaskHandle        mAnalogTaskHandle;
	uInt8             mDigitalBuffer[1];
	float64            * mAnalogBuffer;
	float64            * mTemplateBuffer;
	std::string			mAnalogDeviceName;
	std::string		    mDigitalDeviceName;
	std::string			mAnalogPortSpec;
	std::string			mDigitalPortSpec;
	bool				mAnalogUse;
	bool				mDigitalUse;
	std::string			mAnalogState;
	std::string			mDigitalState;
	std::string			mAnalogDevice;
	double				mNumberOfSamples;
	int					mStimType;
	bool				mBiphasic;
	bool				mDS5;
	bool				mDS8;
	int					mAORange;
	uInt16				initialCurrent ;
	double				maxValue;
	bool				mRestartSetTrigger;
	double				CurrentAmplitudemaxValue;
	double				mMaxValue;			
	int					mStimPhaseNSamples[3];
	double				mSampleRate;
	double				mPulseWidth;
	double				mInterphasicDelay;
	std::vector<Expression>   mExpressions;          //  the Expressions being used by the filter
	int ParseMatrix(
		std::string			& AnalogDeviceName,
		std::string		    & DigitalDeviceName,
		std::string			& AnalogPortSpec,
		std::string			& DigitalPortSpec,
		bool				& AnalogUse,
		bool				& DigitalUse,
		std::string			& AnalogState,
		std::string			& DigitalState,
		std::string			& aDeviceName
		) const;
	void writeAnalogBuffer(double Val, double NumberOfSamples, float64 * &AnalogBuffer, int StimType, int Steps);
	int NoSamplesCalc(int* output, double SamplingFrequency, double PulseWidth, double InterphasicDelay, bool Biphasic, int R);
	void WaveFormGenerate_phase13(int StimType, double NumberOfSamples, float64* &StimBuffer,float Amp,int offset, float PulseWidth, double SamplingFrequency);
	void WaveFormGenerate_phase2(double NumberOfSamples, float64* &StimBuffer,int offset);
	void ConstructStimWaveform(float64* &StimBuffer,int StimTypeN,int StimTypeP, double SamplingFrequency, double PulseWidth, double InterphasicDelay, bool Biphasic,int R, double Amp, int NumberSamples, int* StimPhaseNSamples);
};

#endif // INCLUDED_TEST_H
