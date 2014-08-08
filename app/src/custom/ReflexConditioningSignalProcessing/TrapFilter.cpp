////////////////////////////////////////////////////////////////////////////////
// $Id: $
// Authors: Jeremy Hill <jezhill@gmail.com>
// Description: TrapFilter implementation
//
//
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
////////////////////////////////////////////////////////////////////////////////
#include "PCHIncludes.h"
#pragma hdrstop

#include "TrapFilter.h"
#include "BCIStream.h"

#ifdef    WORKAROUND4530
#include "Workaround4530.h"
#else
#define IN_SECONDS_W4530( x ) Parameter( x ).InSeconds()
#define IN_VOLTS_W4530( x )   Parameter( x ).InVolts()
#endif // WORKAROUND4530

using namespace std;

RegisterFilter( TrapFilter, 2.Q );

TrapFilter::TrapFilter() :
mVis( NULL ),
mRingBuffer( NULL ),
mOutput( NULL )
{
  
}

TrapFilter::~TrapFilter()
{
  Halt();
}

void
TrapFilter::Publish()
{

  BEGIN_PARAMETER_DEFINITIONS
    "Trigger:Trigger%20Detection   string     TriggerChannel=            3      3     % % // name or index of the input channel used to monitor the trigger",
    "Trigger:Trigger%20Detection   float      TriggerThreshold=          1.0V   1.0V  0 % // voltage that the trigger must exceed to be counted as a rising edge",
    "Trigger:Epoch                 stringlist ChannelsToTrap=      1     2      2     % % // names or indices of the input channels to be trapped",
    "Trigger:Epoch                 float      LookForward=             150ms  150ms   1 % // length of signal segment to capture after each trigger",
    "Trigger:Epoch                 float      LookBack=                 75ms   75ms   1 % // length of signal segment to capture before each trigger",
    "Visualize:Processing%20Stages int        VisualizeTrapFilter=       1      1     0 1 // Visualize TrapFilter output (boolean)",
  END_PARAMETER_DEFINITIONS

  BEGIN_STATE_DEFINITIONS
    "TrialsCompleted 16 0 0 0",
  END_STATE_DEFINITIONS
}

void
TrapFilter::Halt()
{
  delete mVis; mVis = NULL;
  delete mRingBuffer; mRingBuffer = NULL;
  delete mOutput; mOutput = NULL;
}

void
TrapFilter::Preflight( const SignalProperties& InputProperties, SignalProperties& OutputProperties ) const
{
  OutputProperties = InputProperties;
  OutputProperties.SetIsStream( false );
  int nChannelsOfInterest = Parameter( "ChannelsToTrap" )->NumValues();
  OutputProperties.SetChannels( nChannelsOfInterest );
  for( int i = 0; i < nChannelsOfInterest; i++ )
  {
    string entry = Parameter( "ChannelsToTrap" )( i );
    int channelOfInterest = ( int )InputProperties.ChannelIndex( entry );
    if( channelOfInterest < 0 )
      bcierr << "invalid or unrecognized channel " << entry << " in ChannelsToTrap parameter" << endl;
    else
      OutputProperties.ChannelLabels()[ i ] = InputProperties.ChannelLabels()[ channelOfInterest ];
  }
  int lookForwardSamples = ( int )( 0.5 + IN_SECONDS_W4530( "LookForward" ) * InputProperties.SamplingRate() );
  int lookBackSamples    = ( int )( 0.5 + IN_SECONDS_W4530( "LookBack"    ) * InputProperties.SamplingRate() );
  OutputProperties.SetElements( lookForwardSamples + lookBackSamples );
  OutputProperties.ElementUnit().SetOffset( ( double )lookBackSamples );
  
  if( InputProperties.ChannelIndex( ( string )Parameter( "TriggerChannel" ) ) < 0 )
    bcierr << "invalid or unrecognized channel " << ( string )Parameter( "TriggerChannel" ) << " in TriggerChannel parameter" << endl;
  
  IN_VOLTS_W4530( "TriggerThreshold" );
}


void
TrapFilter::Initialize( const SignalProperties& InputProperties, const SignalProperties& OutputProperties )
{
  mInputGain = InputProperties.ValueUnit().Gain();
  mInputOffset = InputProperties.ValueUnit().Offset();
  if( InputProperties.ValueUnit().Symbol() != "V" )
    bcierr << "internal error: input signal values are expressed in " << InputProperties.ValueUnit().Symbol() << ", not V - do not know how to handle this" << endl;
  if( InputProperties.ElementUnit().Symbol() != "s" )
    bcierr << "internal error: input element values are expressed in " << InputProperties.ElementUnit().Symbol() << ", not s - do not know how to handle this" << endl;

  mChannelIndices.clear();
  int nChannelsOfInterest = Parameter( "ChannelsToTrap" )->NumValues();
  for( int i = 0; i < nChannelsOfInterest; i++ )
    mChannelIndices.push_back( ( int )InputProperties.ChannelIndex( ( string )Parameter( "ChannelsToTrap" )( i ) ) );
  mTriggerChannelIndex = ( int )InputProperties.ChannelIndex( ( string )Parameter( "TriggerChannel" ) );
  mLookForwardSamples = ( int )( 0.5 + IN_SECONDS_W4530( "LookForward" ) * InputProperties.SamplingRate() );
  mLookBackSamples    = ( int )( 0.5 + IN_SECONDS_W4530( "LookBack"    ) * InputProperties.SamplingRate() );
  mRingBufferSize = mLookBackSamples + mLookForwardSamples;
  mTriggerThreshold = IN_VOLTS_W4530( "TriggerThreshold" );
  mOutput = new GenericSignal( OutputProperties );
  mRingBuffer = new GenericSignal( OutputProperties );
  
  mVisualize = int( Parameter( "VisualizeTrapFilter" ) );
  if( mVisualize )
  {
    mVis = new GenericVisualization( "TRAPF" );
    mVis->Send( OutputProperties );
    mVis->Send( CfgID::NumSamples, OutputProperties.Elements() );
    mVis->Send( GenericSignal( OutputProperties ) );
  }
}

void
TrapFilter::StartRun()
{
  mSamplesSinceLastTrigger = mLookForwardSamples + 1; // just has to be larger than mLookForwardSamples
  mTriggerStateOnPreviousSample = true; // don't trigger if the trigger voltage is high on the first sample of the run: wait for it to go low, then high again
  mRingBufferCursor = 0;
  mSamplesSeen = 0;
  State( "TrialsCompleted" ) = 0;
  for( int ch = 0; ch < mOutput->Channels(); ch++ )
    for( int el = 0; el < mRingBufferSize; el++ )
      ( *mRingBuffer )( ch, el ) = ( *mOutput )( ch, el ) = 0;
  if( mVisualize )
    mVis->Send( CfgID::WindowTitle, "TrapFilter: waiting for first trigger" );
}


void
TrapFilter::Process( const GenericSignal& InputSignal, GenericSignal& OutputSignal )
{
  for( int inputElement = 0; inputElement < InputSignal.Elements(); inputElement++ )
  {
    double val = InputSignal( mTriggerChannelIndex, inputElement );
    val = ( val - mInputOffset ) * mInputGain; // val is now in Volts, like mTrigggerThreshold
    bool currentTriggerState = ( val >= mTriggerThreshold );
    mSamplesSeen++;
    if( currentTriggerState && !mTriggerStateOnPreviousSample && mSamplesSinceLastTrigger >= mLookForwardSamples )
    {
      bciout << "Trigger detected on sample " << mSamplesSeen << endl;
      mSamplesSinceLastTrigger = 0;
    }
    mTriggerStateOnPreviousSample = currentTriggerState;
    for( unsigned int outputChannelIndex = 0; outputChannelIndex < mChannelIndices.size(); outputChannelIndex++ )
    {
      int inputChannelIndex = mChannelIndices[ outputChannelIndex ];
      ( *mRingBuffer )( outputChannelIndex, mRingBufferCursor ) = InputSignal( inputChannelIndex, inputElement );
    }
    mRingBufferCursor = ( mRingBufferCursor + 1 ) % mRingBufferSize;
    mSamplesSinceLastTrigger++;
    if( mSamplesSinceLastTrigger == mLookForwardSamples )
    {
      int readCursor = mRingBufferCursor; // start at the oldest sample (which is the one that will be overwritten on the next iteration)
      for(int outputElement = 0; outputElement < mRingBufferSize; outputElement++, readCursor = ( readCursor + 1 ) % mRingBufferSize )
        for(int ch = 0; ch < mOutput->Channels(); ch++ )
          ( *mOutput )( ch, outputElement ) = ( *mRingBuffer )( ch, readCursor );
      State( "TrialsCompleted" ) = State( "TrialsCompleted" ) + 1;
      if( mVisualize)
      {
        stringstream ss;
        ss << "TrapFilter: trial #" << State( "TrialsCompleted" );
        mVis->Send( CfgID::WindowTitle, ss.str() );
      }
    }
  }
  OutputSignal = *mOutput;
  if( mVisualize )
    mVis->Send( OutputSignal );
}
