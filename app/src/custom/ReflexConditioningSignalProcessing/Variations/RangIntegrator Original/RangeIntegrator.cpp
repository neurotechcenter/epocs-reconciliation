////////////////////////////////////////////////////////////////////////////////
// $Id: $
// Authors: 
// Description: RangeIntegrator implementation
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

#include "RangeIntegrator.h"
#include "BCIStream.h"
#include "StringUtils.h"

#ifdef    WORKAROUND4530
#include "Workaround4530.h"
#endif // WORKAROUND4530

using namespace std;


RegisterFilter( RangeIntegrator, 2.E );


RangeIntegrator::RangeIntegrator()
{
  
}

RangeIntegrator::~RangeIntegrator()
{
  Halt();
}

void
RangeIntegrator::Publish()
{
 BEGIN_PARAMETER_DEFINITIONS
   "Responses:Response%20Magnitudes matrix ResponseDefinition= "
               " 1 { Input%20Channel Start   End   Subtract%20Mean? Norm   Weight  Response%20Name } "
               "         1          28ms    35ms        no          1      1.0          H            "
               " % % % // define the response signals:",
   "Responses:Response%20Magnitudes matrix ResponseAssessment= 1 { Response%20Name Min%20Amplitude Max%20Amplitude Feedback%20Weight }   H 5mV 15mV 1.0 % % % // process the response signals:",
   "Responses:Response%20Magnitudes int    OutputMode= 0 0 0 1 // which signal to pass on, 0: pass through input unchanged, 1: output responses (enumeration)",

 END_PARAMETER_DEFINITIONS
  
 BEGIN_STATE_DEFINITIONS 
   "ResponseFeedbackValue 32 0 0 0",
   "ResponseGreen          1 0 0 0",
   "SuccessfulTrials      16 0 0 0",
 END_STATE_DEFINITIONS
 
}

void
RangeIntegrator::ParseMatrices(

  std::vector<int>    & inputChannelIndices,
  std::vector<int>    & startSamples,
  std::vector<int>    & stopSamples,
  std::vector<bool>   & subtractMeanFlags,
  std::vector<double> & norms,
  std::vector<double> & weights,
  std::vector<int>    & responseChannelIndices,

  std::vector<int>    & assessmentIndices,
  std::vector<double> & minValues,
  std::vector<double> & maxValues,
  std::vector<double> & feedbackWeights,

  const SignalProperties &  InputProperties,
  SignalProperties &  responseProperties

) const
{
  std::vector<std::string> responseChannelNames;
  
  responseProperties = InputProperties;
  responseProperties.SetElements( 1 );
  responseProperties.ElementLabels().Resize( 1 );
  responseProperties.ElementLabels()[ 0 ] = "1";
  responseProperties.ElementUnit().SetOffset( 0.0 );
  responseProperties.ElementUnit().SetGain( ( double ) Parameter( "SampleBlockSize" ) / Parameter( "SamplingRate" ).InHertz() );
  responseProperties.ElementUnit().SetSymbol( "s" );

  inputChannelIndices.clear();
  startSamples.clear();
  stopSamples.clear();
  subtractMeanFlags.clear();
  norms.clear();
  weights.clear();
  responseChannelIndices.clear();

  string paramName = "ResponseDefinition";
  ParamRef definitionMatrix = Parameter( paramName );
  if( definitionMatrix->NumColumns() != 7 )
  {
    bcierr << paramName << " parameter must have 7 columns" << endl;
    return;
  }
  int lookBackSamples = ( int )( 0.5 + InputProperties.ElementUnit().Offset() ); // TODO: verify this works!
  double minTimeMsec = 1000.0 * -lookBackSamples / ( double )InputProperties.SamplingRate();
  double maxTimeMsec = 1000.0 * ( -lookBackSamples + InputProperties.Elements() ) / ( double )InputProperties.SamplingRate();
  for( int row = 0; row < definitionMatrix->NumRows(); row++ )
  {
    int col = -1;
    
    string inputChannelString = StringUtils::Strip( definitionMatrix( row, ++col ) );
    int inputChannelIndex = ( int )InputProperties.ChannelIndex( inputChannelString );
    if( inputChannelIndex < 0 )
      bcierr << "Invalid input channel specification \"" << inputChannelString << "\" in " << paramName << " parameter, row " << row + 1 << ", column " << col + 1 << endl;
    inputChannelIndices.push_back( inputChannelIndex );
    
    double startSec = definitionMatrix( row, ++col ).InSeconds();  // TODO: will this issue a reasonable error message if the entry is not valid?
    int startSample = ( int )( 0.5 + startSec * ( double )InputProperties.SamplingRate() );
    startSample += lookBackSamples;
    if( startSample < 0 || startSample >= InputProperties.Elements() ) // that's right, greater-than-or-equal-to is the right operator for the start sample
      bcierr << "start time " << startSec * 1000.0 << "ms (" << paramName << " parameter, row " << row + 1 << ", column " << col + 1 << ") lies outside the available interval [" <<  minTimeMsec << "ms, " << maxTimeMsec << "ms]" << endl;
    startSamples.push_back( startSample );

    double endSec = definitionMatrix( row, ++col ).InSeconds();  // TODO: will this issue a reasonable error message if the entry is not valid?
    double durationSec = endSec - startSec;
    int durationSamples = ( int )( 0.5 + durationSec * ( double )InputProperties.SamplingRate() );
    int stopSample = startSample + durationSamples;
    if( stopSample < 0 || stopSample > InputProperties.Elements() ) // that's right, greater-than is the right operator for the end sample
      bcierr << "end time " << endSec * 1000.0 << "ms (" << paramName << " parameter, row " << row + 1 << ", column " << col + 1 << ") lies outside the available interval [" <<  minTimeMsec << "ms, " << maxTimeMsec << "ms]" << endl;
    if( durationSamples == 0 )
      bcierr << "start and end time [" << startSec * 1000.0 << "ms, " << endSec * 1000.0 << "ms] are too close together (<1 sample) in " << paramName << " parameter, row " << row + 1 << ", columns " << col << " and " << col + 1 << endl;
    if( durationSamples < 0 )
      bcierr << "start time (" << startSec * 1000.0 << "ms) is after end time (" << endSec * 1000.0 << "ms)  in " << paramName << " parameter, row " << row + 1 << ", columns " << col << " and " << col + 1 << endl;
    stopSamples.push_back( stopSample );
    
    //               " 1 { Input%20Channel Start   End   Subtract%20Mean? Norm   Weight  Response%20Name } "
    //               "         1          28ms   35ms        no           1      1.0           H           "

    string entry = StringUtils::Strip( definitionMatrix( row, ++col ) );
    string flag = StringUtils::ToLower( entry );
    if( flag == "no" || flag == "false" || flag == "0" || flag == "off" )
      subtractMeanFlags.push_back( false );
    else if( flag == "yes" || flag == "true" || flag == "1" || flag == "on" )
      subtractMeanFlags.push_back( true );
    else
      bcierr << "could not interpret \"" << entry << "\" as a boolean in " << paramName << " parameter (row " << row + 1 << ", column " << col + 1 << ")" << endl;
    
    ParamRef cell = definitionMatrix( row, ++col );
    string normString = StringUtils::Strip( cell );
    double norm;
    if( normString.size() == 0 )
      norm = 0.0;
    else
      norm = cell;  // TODO: will this issue a reasonable error message if the entry is not valid?
    if( norm < 0.0 )
      bcierr << "norm values may not be negative in " << paramName << " parameter (value is " << norm << " at row " << row + 1 << ", column " << col + 1 << ")" << endl;
    norms.push_back( norm );
    
    double weight = definitionMatrix( row, ++col );  // TODO: will this issue a reasonable error message if the entry is not valid?
    weights.push_back( weight );
    
    string responseChannelString = StringUtils::Strip( definitionMatrix( row, ++col ) );
    if( responseChannelString.size() == 0 )
      bcierr << "response names cannot be blank (" << paramName << " parameter, row " << row + 1 << ", column " << col + 1 << ")" << endl;
    unsigned int responseChannelIndex;
    for( responseChannelIndex = 0; responseChannelIndex < responseChannelNames.size(); responseChannelIndex++ )
      if( StringUtils::ToLower( responseChannelString ) == StringUtils::ToLower( responseChannelNames[ responseChannelIndex ] ) )
        break;
    if( responseChannelIndex == responseChannelNames.size() )
      responseChannelNames.push_back( responseChannelString );
    responseChannelIndices.push_back( responseChannelIndex );
  }
  responseProperties.SetChannels( responseChannelNames.size() );
  for( int i = 0; i < responseProperties.Channels(); i++ )
    responseProperties.ChannelLabels()[ i ] = responseChannelNames[ i ];
    
  assessmentIndices.clear();
  minValues.clear();
  maxValues.clear();
  feedbackWeights.clear();
  paramName = "ResponseAssessment";
  ParamRef assessmentMatrix = Parameter( paramName );
  if( assessmentMatrix->NumColumns() != 4 )
  {
    bcierr << paramName << " parameter must have 4 columns" << endl;
    return;
  }
  for( int row = 0; row < assessmentMatrix->NumRows(); row++ )
  {
    int col = -1;
    
    string responseNameString = StringUtils::Strip( assessmentMatrix( row, ++col ) );
    int responseIndex = ( int )responseProperties.ChannelIndex( responseNameString );
    if( responseIndex < 0 )
      bcierr << "Invalid response specification \"" << responseNameString << "\" in " << paramName << " parameter, row " << row + 1 << ", column " << col + 1 << "(does not match any of the responses defined in ResponseDefinition parameter)" << endl;
    assessmentIndices.push_back( responseIndex );
    
    ParamRef minParam = assessmentMatrix( row, ++col );
    ParamRef maxParam = assessmentMatrix( row, ++col );
    double minValue = -Inf<double>();
    double maxValue = +Inf<double>();
    if( ( ( string )minParam ).length() ) minValue = minParam.InVolts();
    if( ( ( string )maxParam ).length() ) maxValue = maxParam.InVolts();
    if( minValue >= maxValue )
      bcierr << "minimum value (" << minValue * 1000.0 << "mV) should be less than maximum value (" << maxValue * 1000.0 << "mV) in " << paramName << " parameter (row " << row + 1 << ", columns " << col << "-" << col + 1 << ")" << endl;
    minValues.push_back( minValue );
    maxValues.push_back( maxValue );
    
    double weight = assessmentMatrix( row, ++col );  // TODO: will this issue a reasonable error message if the entry is not valid?
    feedbackWeights.push_back( weight );
  }
}

void
RangeIntegrator::Halt()
{
  
}

void
RangeIntegrator::Preflight( const SignalProperties & InputProperties, SignalProperties & OutputProperties ) const
{
  std::vector<int>    inputChannelIndices;
  std::vector<int>    startSamples;
  std::vector<int>    stopSamples;
  std::vector<bool>   subtractMeanFlags;
  std::vector<double> norms;
  std::vector<double> weights;
  std::vector<int>    responseChannelIndices;
  std::vector<int>    assessmentIndices;
  std::vector<double> minValues;
  std::vector<double> maxValues;
  std::vector<double> feedbackWeights;
  
  SignalProperties responseProperties;
  ParseMatrices( inputChannelIndices, startSamples, stopSamples, subtractMeanFlags, norms, weights, responseChannelIndices,
                 assessmentIndices, minValues, maxValues, feedbackWeights,
                 InputProperties, responseProperties );
  if( Parameter( "OutputMode" ) == 0 )
    OutputProperties = InputProperties;
  else
    OutputProperties = responseProperties;
  
  if( States->Exists( "TrialsCompleted" ) ) State( "TrialsCompleted" );
}

void
RangeIntegrator::Initialize( const SignalProperties & InputProperties, const SignalProperties & OutputProperties )
{
  mInputGain = InputProperties.ValueUnit().Gain();
  mInputOffset = InputProperties.ValueUnit().Offset();
  if( InputProperties.ValueUnit().Symbol() != "V" )
    bcierr << "internal error: input signal values are expressed in " << InputProperties.ValueUnit().Symbol() << ", not V - do not know how to handle this" << endl;
  if( InputProperties.ElementUnit().Symbol() != "s" )
    bcierr << "internal error: input element values are expressed in " << InputProperties.ElementUnit().Symbol() << ", not s - do not know how to handle this" << endl;
    
  mPassThrough = ( Parameter( "OutputMode" ) == 0 );

  ParseMatrices( mInputChannelIndices, mStartSamples, mStopSamples, mSubtractMeanFlags, mNorms, mWeights, mResponseChannelIndices,
                 mAssessmentIndices, mMinValues, mMaxValues, mFeedbackWeights,
                 InputProperties, mResponseProperties );

  mComputeMeans = false;
  for( unsigned int i = 0; i < mSubtractMeanFlags.size(); i++ )
    if( mSubtractMeanFlags[ i ] )
      mComputeMeans = true;
}

void
RangeIntegrator::StartRun()
{
  mTrialsCompleted = 0;
  State( "SuccessfulTrials" ) = 0;
}

void
RangeIntegrator::Process( const GenericSignal & InputSignal, GenericSignal & OutputSignal )
{
  int nComponents = mInputChannelIndices.size();
  int nResponses = mResponseProperties.Channels();
  std::vector<double> means;
  if( mComputeMeans )
  {
    int nChannels = InputSignal.Channels();
    int nSamples  = InputSignal.Elements();
    for( int ch = 0; ch < InputSignal.Channels(); ch++ )
    {
      double sum = 0.0;
      for( int el = 0; el < InputSignal.Elements(); el++ )
      {
        double val = InputSignal( ch, el );
        val = ( val - mInputOffset ) * mInputGain; // now expressed in Volts
        sum += val;
      }
      means.push_back( sum / ( double )InputSignal.Elements() );
    }
  }
  GenericSignal responseSignal( mResponseProperties ); // zeroed already  
  for( int i = 0; i < nComponents; i++ )
  {
    int ch = mInputChannelIndices[ i ];
    double magnitude = 0.0;
    double mean = mSubtractMeanFlags[ i ] ? means[ ch ] : 0.0;
    int nSamples = mStopSamples[ i ] - mStartSamples[ i ];
    for( int el = mStartSamples[ i ]; el < mStopSamples[ i ]; el++ )
    {
      double val = InputSignal( ch, el );
      val = ( val - mInputOffset ) * mInputGain; // now expressed in Volts
      val -= mean;
      if( mNorms[ i ] )
        val = ::pow( ::fabs( val ), mNorms[ i ] );
      magnitude += val / ( double )nSamples;
    }
    if( mNorms[ i ] != 0.0 && mNorms[ i ] != 1.0 )
      magnitude = ::pow( magnitude, 1.0 / mNorms[ i ] );
    responseSignal( mResponseChannelIndices[ i ], 0 ) += magnitude * mWeights[ i ];
  }
  double feedbackValue = 0.0;
  bool success = true;
  for( unsigned int i = 0; i < mAssessmentIndices.size(); i++ )
  {
    double response = responseSignal( mAssessmentIndices[ i ], 0 );
    if( response < mMinValues[ i ] || response > mMaxValues[ i ] ) success = false;
    feedbackValue += mFeedbackWeights[ i ] * response;
  }
  State( "ResponseGreen" ) = success;
  int trialsCompleted = OptionalState( "TrialsCompleted", 0 );
  if( trialsCompleted > mTrialsCompleted )
    State( "SuccessfulTrials" ) = State( "SuccessfulTrials" ) + success;
  mTrialsCompleted = trialsCompleted;

  feedbackValue *= 1e6; // feedbackValue is now in microvolts
  
  double maxValue = ::pow( 2.0, State( "ResponseFeedbackValue" )->Length() - 1.0 ) - 1.0;
  feedbackValue = ( ( feedbackValue < maxValue ) ? feedbackValue : maxValue );
  feedbackValue = ( ( feedbackValue > 0 ) ? feedbackValue : 0 );
  State( "ResponseFeedbackValue" ) = ( unsigned int )( 0.5 + feedbackValue );
  
  if( mPassThrough )
    OutputSignal = InputSignal;
  else
    OutputSignal = responseSignal;
}
