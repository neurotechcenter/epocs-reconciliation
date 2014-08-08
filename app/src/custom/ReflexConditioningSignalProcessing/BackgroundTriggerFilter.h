////////////////////////////////////////////////////////////////////////////////
// $Id: $
// Authors: 
// Description: BackgroundTriggerFilter header
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

#ifndef INCLUDED_BackgroundTriggerFilter_H  // makes sure this header is not included more than once
#define INCLUDED_BackgroundTriggerFilter_H

#include "GenericFilter.h"
#include "Expression.h"
#include "RandomGenerator.h"

class BackgroundTriggerFilter : public GenericFilter
{
 public:
           BackgroundTriggerFilter();
  virtual ~BackgroundTriggerFilter();
  virtual void Publish();
  virtual void Halt();
  virtual void Preflight(  const SignalProperties& Input,       SignalProperties& Output ) const;
  virtual void Initialize( const SignalProperties& Input, const SignalProperties& Output );
  virtual void StartRun();
  virtual void Process(    const GenericSignal&    Input,       GenericSignal&    Output );

  virtual bool AllowsVisualization() const { return false; } // disable the default visualization mechanism so that we can implement our own

 private:
  class RingBuffer : public GenericSignal {
   public:
     RingBuffer( int nChannels, int nElements ) : GenericSignal( nChannels, nElements ) { mCursor = 0; }
     RingBuffer( const SignalProperties & props ) : GenericSignal( props ) { mCursor = 0; }
     void Advance() { if( ++mCursor >= Elements() ) mCursor = 0; }
     int mCursor;
  };

  bool mVisualize;
  GenericVisualization * mVis;
  RingBuffer * mSegmentBuffer;
  RingBuffer * mFeedbackBuffer;
  GenericSignal * mSegmentAmplitudes;
  int mNumberOfBackgroundChannels;
  int mSegmentsToDiscard;
  int mMinNumberOfSegments;
  int mMaxNumberOfSegments;
  int mSamplesPerSegment;
  unsigned long mSamplesSeen;
  int mRefractoryBlocks;
  int mBlocksSinceLastTrigger;
  int mTriggerDurationBlocks;
  std::vector<int>    mChannelIndices;
  std::vector<bool>   mSubtractMeanFlags;
  std::vector<double> mNorms;
  std::vector<double> mMinAmplitudes;
  std::vector<double> mMaxAmplitudes;
  std::vector<double> mFeedbackChannelWeights;
  bool mUseTriggerExpression;
  Expression mTriggerExpression;
  double mInputGain;
  double mInputOffset;
  double mMonitoringGain;
  double mMonitoringOffset;
  RandomGenerator mRandomGenerator;

  void ChooseNumberOfSegments();
  void ZeroSignal( GenericSignal * signal );
  double ComputeBackgroundValue( RingBuffer * ringBuffer, int channelIndex, int startSample, int nSamples, double subtract, double norm );
  int ParseMatrix(
    std::vector<int>    & channelIndices,
    std::vector<bool>   & subtractMeanFlags,
    std::vector<double> & norms,
    std::vector<double> & minValues,
    std::vector<double> & maxValues,
    std::vector<double> & feedbackChannelWeights,
    const SignalProperties & InputProperties,
    SignalProperties & OutputProperties
  ) const;
};

#endif // INCLUDED_BackgroundTriggerFilter_H
