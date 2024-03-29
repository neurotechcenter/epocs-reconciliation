////////////////////////////////////////////////////////////////////////////////
// $Id: $
// Authors: Jeremy Hill <jezhill@gmail.com>
// Description: BackgroundTriggerFilter implementation
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

#include "BackgroundTriggerFilter.h"
#include "BCIStream.h"
#include "StringUtils.h"

#ifdef    WORKAROUND4530
#include "Workaround4530.h"
#endif // WORKAROUND4530

using namespace std;


RegisterFilter( BackgroundTriggerFilter, 2.P );

BackgroundTriggerFilter::BackgroundTriggerFilter() :
  mVis( NULL ),
  mSegmentBuffer( NULL ),
  mFeedbackBuffer( NULL ),
  mSegmentAmplitudes( NULL ),
  mMonitoringGain( 1e-3 ), // express and visualize the segment amplitudes in millivolts (or whatever the BackgroundVisualizationUnit parameter specifies)
  mMonitoringOffset( 0.0 ),
  mRandomGenerator( this )
{
  
}

BackgroundTriggerFilter::~BackgroundTriggerFilter()
{
  Halt();
}

void
BackgroundTriggerFilter::Publish()
{

  BEGIN_PARAMETER_DEFINITIONS
    "Background:Triggering%20Conditions matrix     BackgroundChannels= "
                   " 2 { Input%20Channel Subtract%20Mean? Norm Min%20Amplitude Max%20Amplitude Feedback%20Weight } "
                   "          EMG1              yes         1       10mV           25mV               1.0          "
                   "          EMG2              yes         1        0mV           15mV               0.0          "
                   " % % % // specification of signal channels used to monitor baseline compliance",
    "Background:Triggering%20Conditions float      BackgroundHoldDuration=               2s     2s   0 % // the duration for which consecutive time segments must comply with the target baseline activity ranges",
    "Background:Triggering%20Conditions float      MaxRandomExtraHoldDuration=           1s     1s   0 % // a random extra duration may be added to BackgroundHoldDuration on each trial, up to this amount",
    "Background:Triggering%20Conditions float      BackgroundSegmentDuration=          200ms  200ms  1 % // the duration of one background segment in sampleblocks (or in milliseconds if \"ms\" is appended)",
    "Background:Background%20Feedback   float      FeedbackTimeConstant=               200ms  200ms  0 % // length of time over which to average the feedback signal (will be rounded up to a whole number of segment lengths)",
    "Background:Background%20Feedback   float      BackgroundFreezeTime=              1000ms 1000ms  0 % // after a trigger is triggered, the background bar's height and color will be frozen for this duration (expressed in sampleblocks, or milliseconds if \"ms\" is appended)",

       "Trigger:Triggering%20Conditions string     TriggerExpression=                    %      %    % % // optional BCI2000 Expression that must be satisfied for trigger to fire",
       "Trigger:Trigger%20Output        float      TriggerStateDuration=                 2      2    1 % // duration (whole number of sampleblocks) for which the EnableTrigger output state is kept high",
       "Trigger:Triggering%20Conditions float      MinTimeBetweenTriggers=               5s     5s   2 % // trigger refractory time in sampleblocks (or in seconds if \"s\" is appended)",

    "Visualize:Processing%20Stages      int        VisualizeBackgroundAverages=          0      0    0 1 // Visualize segment averages from BackgroundTriggerFilter (boolean)",
    "Visualize:Processing%20Stages      float      BackgroundVisualizationUnit=          1mV    1mV  0 % // Unit for numerical representation of BackgroundTriggerFilter",
  END_PARAMETER_DEFINITIONS

  // TODO: For recruitment curves, TriggerExpression could be StimulationIntensity!=0,  but some mechanism
  //       (in the application?) will need to set StimulationIntensity to 0 whenever a trigger occurs.
  //       Here's one scripting-based possibility, but not sure if it will work, and it will mean
  //       StimulationIntensity is at 0 when the response actually comes in:
  //           add state StimulationIntensity
  //           set parameter TriggerExpression "EnableTrigger?(State(StimulationIntensity):=0):0;StimulationIntensity!=0"
  //       Furthermore, we need an input interface to StimulationIntensity, and an output of the recruitment curve data
  // 
  
  BEGIN_STATE_DEFINITIONS
    "BackgroundFeedbackValue    32 0 0 0",
    "BackgroundGreen             1 0 0 0",
    "EnableTrigger               1 0 0 0",
    "TriggerExpressionSatisfied  1 0 0 0",
  END_STATE_DEFINITIONS

}
void
BackgroundTriggerFilter::Halt()
{
  delete mVis; mVis = NULL;
  delete mSegmentBuffer; mSegmentBuffer = NULL;
  delete mFeedbackBuffer; mFeedbackBuffer = NULL;
  delete mSegmentAmplitudes; mSegmentAmplitudes = NULL;
}

int
BackgroundTriggerFilter::ParseMatrix(
  std::vector<int>    & channelIndices,
  std::vector<bool>   & subtractMeanFlags,
  std::vector<double> & norms,
  std::vector<double> & minValues,
  std::vector<double> & maxValues,
  std::vector<double> & feedbackChannelWeights,
  const SignalProperties & InputProperties,
  SignalProperties & segmentProperties
) const
{
  double monitoringOffset = 0.0, monitoringGain = Parameter( "BackgroundVisualizationUnit" ).InVolts();
  string paramName = "BackgroundChannels";
  ParamRef matrix = Parameter( paramName );
  segmentProperties = InputProperties;
  int nBackgroundChannels = matrix->NumRows();
  segmentProperties.SetChannels( max( 1, nBackgroundChannels ) );
  if( matrix->NumColumns() != 6 )
  {
    bcierr << paramName << " parameter must have 6 columns" << endl;
    return nBackgroundChannels;
  }
  channelIndices.clear();
  subtractMeanFlags.clear();
  norms.clear();
  minValues.clear();
  maxValues.clear();
  feedbackChannelWeights.clear();
  double sumAbsWeights = 0.0;
  for( int row = 0; row < nBackgroundChannels; row++ )
  {
    int col = -1;
    string channelSpec = matrix( row, ++col );
    int channelIndex = ( int )InputProperties.ChannelIndex( channelSpec );
    if( channelIndex < 0 )
      bcierr << "invalid or unrecognized channel " << channelSpec << " in " << paramName <<  " parameter (row " << row + 1 << ", column " << col + 1 << ")" << endl;
    segmentProperties.ChannelLabels()[ row ] = InputProperties.ChannelLabels()[ channelIndex ];
    channelIndices.push_back( channelIndex );

    string entry = StringUtils::Strip( matrix( row, ++col ) );
    string flag = StringUtils::ToLower( entry );
    if( flag == "no" || flag == "false" || flag == "0" || flag == "off" )
      subtractMeanFlags.push_back( false );
    else if( flag == "yes" || flag == "true" || flag == "1" || flag == "on" )
      subtractMeanFlags.push_back( true );
    else
      bcierr << "could not interpret \"" << entry << "\" as a boolean in " << paramName << " parameter (row " << row + 1 << ", column " << col + 1 << ")" << endl;

    double norm = matrix( row, ++col );
    norms.push_back( norm );

    ParamRef minParam = matrix( row, ++col );
    ParamRef maxParam = matrix( row, ++col );
    double minValue = -Inf<double>();
    double maxValue = +Inf<double>();
    if( ( ( string )minParam ).length() ) minValue = minParam.InVolts();
    if( ( ( string )maxParam ).length() ) maxValue = maxParam.InVolts();
    if( minValue >= maxValue )
      bcierr << "minimum value (" << minValue * 1000.0 << "mV) should be less than maximum value (" << maxValue * 1000.0 << "mV) in " << paramName << " parameter (row " << row + 1 << ", columns " << col << "-" << col + 1 << ")" << endl;

    minValue = minValue / monitoringGain + monitoringOffset; // minima are now expressed in the units that we visualize
    minValues.push_back( minValue );
    maxValue = maxValue / monitoringGain + monitoringOffset; // maxima are now expressed in the units that we visualize
    maxValues.push_back( maxValue );

    double weight = matrix( row, ++col );
    sumAbsWeights += ::fabs( weight );
    feedbackChannelWeights.push_back( weight );
  }
  for( int row = 0; row < nBackgroundChannels; row++ )
    feedbackChannelWeights[ row ] /= sumAbsWeights;
  return nBackgroundChannels;
}

void
BackgroundTriggerFilter::Preflight( const SignalProperties& InputProperties, SignalProperties& OutputProperties ) const
{
  OutputProperties = InputProperties; // signal will be passed through unmodified.
  std::vector<int>    channelIndices;
  std::vector<bool>   subtractMeanFlags;
  std::vector<double> norms;
  std::vector<double> minAmplitudes;
  std::vector<double> maxAmplitudes;
  std::vector<double> feedbackChannelWeights;
  SignalProperties segmentProperties;
  ParseMatrix( channelIndices, subtractMeanFlags, norms, minAmplitudes, maxAmplitudes, feedbackChannelWeights, InputProperties, segmentProperties );
  
  double holdDurationSeconds = Parameter( "BackgroundHoldDuration" ).InSeconds();
  double extraHoldDurationSeconds = Parameter( "MaxRandomExtraHoldDuration" ).InSeconds();
  double secondsPerSegment = Parameter( "BackgroundSegmentDuration" ).InSeconds();
  int samplesPerSegment = ( int )( 0.5 + secondsPerSegment * InputProperties.SamplingRate() );
  secondsPerSegment = ( double ) samplesPerSegment / InputProperties.SamplingRate();
  
  double blocks, msecPerBlock = 1000.0 * ( double )Parameter( "SampleBlockSize" ) / ( double )Parameter( "SamplingRate" );

  blocks = Parameter( "TriggerStateDuration" ).InSampleBlocks();
  if( blocks != ::ceil( blocks ) )
    bciwarn << "TriggerStateDuration will be rounded up to " << ::ceil( blocks ) << " whole sample-blocks (=" <<  ::ceil( blocks ) * msecPerBlock << "ms)"  << endl;
    
  blocks = Parameter( "BackgroundFreezeTime" ).InSampleBlocks();
  if( blocks != ::ceil( blocks ) )
    bciwarn << "BackgroundFreezeTime will be rounded up to " << ::ceil( blocks ) << " whole sample-blocks (=" <<  ::ceil( blocks ) * msecPerBlock << "ms)"  << endl;
    
  blocks = Parameter( "MinTimeBetweenTriggers" ).InSampleBlocks();
  if( blocks != ::ceil( blocks ) )
    bciwarn << "MinTimeBetweenTriggers will be rounded up to " << ::ceil( blocks ) << " whole sample-blocks (=" <<  ::ceil( blocks ) * msecPerBlock << "ms)"  << endl;

  string eStr = Parameter( "TriggerExpression" );
  eStr = StringUtils::Strip( eStr );
  if( eStr.size() )
  {
    GenericSignal zeros( InputProperties );
    Expression( eStr ).Evaluate( &zeros, zeros.Elements() - 1 );
  }
  double fbtSec = Parameter( "FeedbackTimeConstant" ).InSeconds();
  if( fbtSec < 0.050 ) bcierr << "FeedbackTimeConstant should not be shorter than 50ms" << endl;
}

void
BackgroundTriggerFilter::Initialize( const SignalProperties& InputProperties, const SignalProperties& OutputProperties )
{
  mMonitoringOffset = 0.0;
  mMonitoringGain = Parameter( "BackgroundVisualizationUnit" ).InVolts();

  mInputGain = InputProperties.ValueUnit().Gain();
  mInputOffset = InputProperties.ValueUnit().Offset();
  if( InputProperties.ValueUnit().Symbol() != "V" )
    bcierr << "internal error: input signal values are expressed in " << InputProperties.ValueUnit().Symbol() << ", not V - do not know how to handle this" << endl;
  if( InputProperties.ElementUnit().Symbol() != "s" )
    bcierr << "internal error: input element values are expressed in " << InputProperties.ElementUnit().Symbol() << ", not s - do not know how to handle this" << endl;

  SignalProperties bufferProperties;
  mNumberOfBackgroundChannels = ParseMatrix(
    mChannelIndices, mSubtractMeanFlags, mNorms,
    mMinAmplitudes, mMaxAmplitudes, mFeedbackChannelWeights,
    InputProperties, bufferProperties
  );
  
  double secondsPerSegment = Parameter( "BackgroundSegmentDuration" ).InSeconds();
  double samplesPerSecond = InputProperties.SamplingRate();
  mSamplesPerSegment = ( int )( 0.5 + secondsPerSegment * samplesPerSecond );

  double holdDurationSeconds = Parameter( "BackgroundHoldDuration" ).InSeconds();
  int holdDurationSamples = ( int )( 0.5 + holdDurationSeconds * samplesPerSecond );
  mMinNumberOfSegments = ( int )::ceil( ( double )holdDurationSamples / ( double )mSamplesPerSegment );
  double roundedHoldDurationSeconds = ( double )( mMinNumberOfSegments * mSamplesPerSegment ) / samplesPerSecond;
  if( ::fabs( holdDurationSeconds - roundedHoldDurationSeconds ) >= 0.5 / samplesPerSecond )
    bciwarn << "BackgroundHoldDuration (" << ( string )Parameter( "BackgroundHoldDuration" ) << ") has been rounded up to " << roundedHoldDurationSeconds << "s to make it an integer number of " << secondsPerSegment * 1000.0 << "ms segments" << endl;

  double extraHoldDurationSeconds = Parameter( "MaxRandomExtraHoldDuration" ).InSeconds();
  int extraHoldDurationSamples = ( int )( 0.5 + extraHoldDurationSeconds * samplesPerSecond );
  int extraSegments = ( int )::ceil( ( double )extraHoldDurationSamples / ( double )mSamplesPerSegment );
  double roundedExtraHoldDurationSeconds = ( double )( extraSegments * mSamplesPerSegment ) / samplesPerSecond;
  if( ::fabs( extraHoldDurationSeconds - roundedExtraHoldDurationSeconds ) >= 0.5 / samplesPerSecond )
    bciwarn << "MaxRandomExtraHoldDuration (" << ( string )Parameter( "MaxRandomExtraHoldDuration" ) << ") has been rounded up to " << roundedExtraHoldDurationSeconds << "s to make it an integer number of " << secondsPerSegment * 1000.0 << "ms segments" << endl;
  mMaxNumberOfSegments = mMinNumberOfSegments + extraSegments;

  mRefractoryBlocks = ( int )::ceil( Parameter( "MinTimeBetweenTriggers" ).InSampleBlocks() );
  mTriggerDurationBlocks = ( int )::ceil( Parameter( "TriggerStateDuration" ).InSampleBlocks() );
  mBlocksToFreezeBackground = ( int )::ceil( Parameter( "BackgroundFreezeTime" ).InSampleBlocks() );
  
  int fbtSamples = ( int )( 0.5 + Parameter( "FeedbackTimeConstant" ).InSeconds() * samplesPerSecond );
  bufferProperties.SetElements( max( 1, fbtSamples ) );
  mFeedbackBuffer = new RingBuffer( bufferProperties );

  bufferProperties.SetElements( mMaxNumberOfSegments * mSamplesPerSegment );
  mSegmentBuffer = new RingBuffer( bufferProperties );

  SignalProperties segmentProperties = bufferProperties;
  segmentProperties.SetIsStream( false );
  segmentProperties.SetName( "Background Segment Amplitudes" );
  segmentProperties.SetElements( mMaxNumberOfSegments );
  segmentProperties.ElementUnit().SetOffset( ( double )( mMaxNumberOfSegments - 1 ) );
  segmentProperties.ElementUnit().SetGain( ( double )mSamplesPerSegment / InputProperties.SamplingRate() );
  segmentProperties.ElementUnit().SetSymbol( "s" );
  segmentProperties.ValueUnit().SetOffset( mMonitoringOffset );
  segmentProperties.ValueUnit().SetGain( mMonitoringGain );
  segmentProperties.ValueUnit().SetSymbol( "V" );

  mSegmentAmplitudes = new GenericSignal( segmentProperties );

  double weightedFeedbackMax = 0.0, denominator = 0.0, inf = Inf<double>();
  for( int i = 0; i < mNumberOfBackgroundChannels; i++ )
  {
    double weight = mFeedbackChannelWeights[ i ];
    double lim = max( ::fabs( mMinAmplitudes[ i ] ), ::fabs( mMaxAmplitudes[ i ] ) );
    if( lim < inf ) { weightedFeedbackMax += weight * lim; denominator += weight; }
  }
  if( denominator ) weightedFeedbackMax /= denominator;
  
  mVisualize = int( Parameter( "VisualizeBackgroundAverages" ) );
  if( mVisualize )
  {
    mVis = new GenericVisualization( "BTRIG" );
    mVis->Send( segmentProperties );
    mVis->Send( CfgID::NumSamples, segmentProperties.Elements() );
    mVis->Send( GenericSignal( segmentProperties ) );
    mVis->Send( CfgID::MinValue, ( weightedFeedbackMax ? -weightedFeedbackMax : -25.0 ) );
    mVis->Send( CfgID::MaxValue, ( weightedFeedbackMax ? +weightedFeedbackMax : +25.0 ) );
  }

  string eStr = Parameter( "TriggerExpression" );
  eStr = StringUtils::Strip( eStr );
  mUseTriggerExpression = eStr.size() > 0;
  if( mUseTriggerExpression )
    mTriggerExpression = Expression( eStr ); 

}

void
BackgroundTriggerFilter::StartRun()
{
  mSamplesSeen = 0;  
  ZeroSignal( mSegmentBuffer );
  ZeroSignal( mFeedbackBuffer );
  mBlocksSinceLastTrigger = 0; // so, at the beginning of the run, we must wait a length of time equal to the normal refractory period
  State( "EnableTrigger" ) = 0;
  State( "BackgroundFeedbackValue" ) = 0;
  State( "BackgroundGreen" ) = 0;
  State( "TriggerExpressionSatisfied" ) = !mUseTriggerExpression;
  ChooseNumberOfSegments();
}

void
BackgroundTriggerFilter::ChooseNumberOfSegments()
{
  mSegmentsToDiscard = ( int )( 0.5 + ( double )( mMaxNumberOfSegments - mMinNumberOfSegments ) * ( double ) mRandomGenerator.Random() / ( double )mRandomGenerator.RandMax() );
}

void
BackgroundTriggerFilter::Process( const GenericSignal& InputSignal, GenericSignal& OutputSignal )
{
  OutputSignal = InputSignal; // Pass the signal through unmodified.
  for( int inputElement = 0; inputElement < InputSignal.Elements(); inputElement++ )
  {
    for( unsigned int outputChannelIndex = 0; outputChannelIndex < mChannelIndices.size(); outputChannelIndex++ )
    {
      int inputChannelIndex = mChannelIndices[ outputChannelIndex ];
      double signal = InputSignal( inputChannelIndex, inputElement );
      if( mSegmentBuffer->Elements()  ) ( *mSegmentBuffer  )( outputChannelIndex, mSegmentBuffer->mCursor  ) = signal;
      if( mFeedbackBuffer->Elements() ) ( *mFeedbackBuffer )( outputChannelIndex, mFeedbackBuffer->mCursor ) = signal;
    }
    mSegmentBuffer->Advance();
    mFeedbackBuffer->Advance();
  }
  mSamplesSeen += InputSignal.Elements();
  
  bool inTheGreen = true;
  bool enableTrigger = true;
  if( mSamplesSeen < ( unsigned long )mSegmentBuffer->Elements() ) enableTrigger = false;
  if( mBlocksSinceLastTrigger < mRefractoryBlocks ) enableTrigger = false;
  
  double combinedFeedbackValue = 0.0;
  for( int bufferedChannel = 0; bufferedChannel < mSegmentBuffer->Channels(); bufferedChannel++ )
  {
    double minAmp = mMinAmplitudes[ bufferedChannel ];
    double maxAmp = mMaxAmplitudes[ bufferedChannel ];
    bool subtractMeanFlag = mSubtractMeanFlags[ bufferedChannel ];
    double norm = mNorms[ bufferedChannel ];

    for( int iSegment = 0; iSegment < mMaxNumberOfSegments; iSegment++ )
    {
      double subtract = 0.0;
      if( subtractMeanFlag )
        subtract = ComputeBackgroundValue( mSegmentBuffer, bufferedChannel, mSamplesPerSegment * iSegment, mSamplesPerSegment, 0.0,      0.0  );
      double amp = ComputeBackgroundValue( mSegmentBuffer, bufferedChannel, mSamplesPerSegment * iSegment, mSamplesPerSegment, subtract, norm );
      if( iSegment >= mSegmentsToDiscard && ( amp < minAmp || amp > maxAmp ) ) enableTrigger = false;
      ( *mSegmentAmplitudes )( bufferedChannel, iSegment ) = amp;
    } // end of iSegment loop

    double subtract = 0.0;
    if( subtractMeanFlag )
      subtract = ComputeBackgroundValue( mFeedbackBuffer, bufferedChannel, 0, mFeedbackBuffer->Elements(), 0.0,      0.0  );
    double amp = ComputeBackgroundValue( mFeedbackBuffer, bufferedChannel, 0, mFeedbackBuffer->Elements(), subtract, norm );
    if( amp < minAmp || amp > maxAmp ) inTheGreen = false;
    combinedFeedbackValue += amp * mFeedbackChannelWeights[ bufferedChannel ];    
  } // end of bufferedChannel loop

  if( mBlocksSinceLastTrigger >= mBlocksToFreezeBackground )
  {
    State( "BackgroundGreen" ) = inTheGreen;
    combinedFeedbackValue = ( combinedFeedbackValue - mMonitoringOffset ) * mMonitoringGain; // now expressed in Volts
    combinedFeedbackValue *= 1e6; // now expressed in microVolts
    double maxValue = ::pow( 2.0, State( "BackgroundFeedbackValue" )->Length() - 1.0 ) - 1.0;
    State( "BackgroundFeedbackValue" ) = ( int )( 0.5 + ( combinedFeedbackValue < maxValue ? combinedFeedbackValue : maxValue ) );
    // NB: luckily, since it is reasonable to express this in microvolts, an unsigned integer provides both plenty of resolution and enough range for practical purposes
  }
  if( mUseTriggerExpression )
  {
    double val = mTriggerExpression.Evaluate( &InputSignal, InputSignal.Elements() - 1 ); 
    State( "TriggerExpressionSatisfied" ) = ( val != 0 );
    enableTrigger = enableTrigger && val;
  }
  
  if( enableTrigger )
  {
    bciout << "Trigger enabled after evaluating sample " << mSamplesSeen << endl; // background-state evaluation works backwards from, and hence includes, the very last sample of the current block
    /*if( mMaxNumberOfSegments - mSegmentsToDiscard )
    {
      for( int iChannel = 0; iChannel < mSegmentAmplitudes->Channels(); iChannel++ )
      {
        stringstream s;
        for( int iSegment = 0; iSegment < mSegmentAmplitudes->Elements(); iSegment++ ) s << ( iSegment == 0 ? "" : ", " ) << ( *mSegmentAmplitudes )( iChannel, iSegment );
        bciout << "Last " << ( mMaxNumberOfSegments - mSegmentsToDiscard ) << " of {" << s.str() << "} are in range for background channel " << ( iChannel + 1 ) << endl;
      }
    }*/
    mBlocksSinceLastTrigger = 0;
    State( "EnableTrigger" ) = 1;
    ChooseNumberOfSegments();
  }
  else
  {
    mBlocksSinceLastTrigger++;
    if( mBlocksSinceLastTrigger >= mTriggerDurationBlocks && State( "EnableTrigger" ) )
      State( "EnableTrigger" ) = 0;
  }
  if( mVisualize )
    mVis->Send( *mSegmentAmplitudes );
}

void
BackgroundTriggerFilter::ZeroSignal( GenericSignal * signal )
{
  for( int ch = 0; ch < signal->Channels(); ch++ )
    for( int el = 0; el < signal->Elements(); el++ )
      ( *signal )( ch, el )  = 0.0;
}

double
BackgroundTriggerFilter::ComputeBackgroundValue( RingBuffer * ringBuffer, int channelIndex, int startSample, int nSamples, double subtract, double norm )
{
  int bufferSize = ringBuffer->Elements();
  int readCursor = ringBuffer->mCursor;   // start at the oldest sample (which is the one that will be overwritten on the next iteration)
  readCursor += startSample;
  double avg = 0.0;
  for( int iSample = 0; iSample < nSamples; iSample++, readCursor++ )
  {
    if( bufferSize ) readCursor %= bufferSize;
    double val = ( *ringBuffer )( channelIndex, readCursor );
    val = ( val - mInputOffset ) * mInputGain; // val is now expressed in Volts
    val = val / mMonitoringGain + mMonitoringOffset; // val is now expressed the same way as mMinAmplitudes and mMaxAmplitudes
    val -= subtract;
    if( norm != 0.0 ) val = ::fabs( val );
    if( norm != 0.0 && norm != 1.0 ) val = ::pow( val, norm );
    avg += val / ( double )nSamples;
  } // end iSample loop
  if( norm != 0.0 && norm != 1.0 ) avg = ::pow( avg, 1.0 / norm );
  return avg;
}

