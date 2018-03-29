////////////////////////////////////////////////////////////////////////////////
// Authors: 
// Description: CurrentControlCriteria header
////////////////////////////////////////////////////////////////////////////////

#ifndef INCLUDED_CURRENTCONTROLCRITERIA_H  // makes sure this header is not included more than once
#define INCLUDED_CURRENTCONTROLCRITERIA_H

#include "GenericFilter.h"
#include "NIDAQmx.imports.h"
#include <string>

class CurrentControlCriteria : public GenericFilter
{
public:
	CurrentControlCriteria();
	~CurrentControlCriteria();
	void Publish() override;
	void Preflight( const SignalProperties& Input, SignalProperties& Output ) const override;
	void Initialize( const SignalProperties& Input, const SignalProperties& Output ) override;
	void StartRun() override;
	void Process( const GenericSignal& Input, GenericSignal& Output ) override;
	void StopRun() override;
	void Halt() override;

private:

	class RingBuffer : public GenericSignal {
	public:
		RingBuffer( int nChannels, int nElements ) : GenericSignal( nChannels, nElements ) { mCursor = 0; }
		void Advance() { if( ++mCursor >= Elements() ) mCursor = 0; }
		int mCursor;
	};

	void CurrentControlCriteria::ZeroSignal( GenericSignal * signal );

	RingBuffer * mReferenceBuffer; //M-Wave Amplitude buffer
	RingBuffer * mResponseBuffer; //H-reflex Amplitude buffer
	RingBuffer * mAvgResponseBuffer; //M-Wave Amplitude Averaged Buffer
	RingBuffer * mAvgReferenceBuffer; //H-reflex Amplitude Averaged Buffer
	int			 nStimuli;
	int			 pTrialsCompleted;
	bool		 mResponseFound;
	 //Current, Delta, minDelta, Threshold
	bool		 StimulusTestControl(unsigned int HAmplitude,uInt16 & CurrentAmplitude, uInt16 & Delta, uInt16 minDelta, double Threshold, bool & mResponseFound);
	uInt16		 mDeltaCurrent;
	uInt16		 mMinDeltaCurrent;
	int 		 mBackgroundFeedbackValue;
	bool		 mUpdateBackground;
	int			 mCriteria;
	uInt16		 mResponseCurrent;
	uInt16		 maxCurrentValue;
	int			 mEnabled;
	float		 mThreshold;
};

#endif // INCLUDED_CURRENTCONTROLCRITERIA_H
