////////////////////////////////////////////////////////////////////////////////
// $Id: $
// Authors: Jeremy Hill <jezhill@gmail.com>
// Description: TrapFilter header
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

#ifndef INCLUDED_TrapFilter_H  // makes sure this header is not included more than once
#define INCLUDED_TrapFilter_H

#include "GenericFilter.h"

class TrapFilter : public GenericFilter
{
 public:
           TrapFilter();
  virtual ~TrapFilter();
  virtual void Publish();
  virtual void Halt();
  virtual void Preflight(  const SignalProperties& Input,       SignalProperties& Output ) const;
  virtual void Initialize( const SignalProperties& Input, const SignalProperties& Output );
  virtual void StartRun();
  virtual void Process(    const GenericSignal&    Input,       GenericSignal&    Output );
  
  virtual bool AllowsVisualization() const { return false; } // disable the default visualization mechanism so that we can implement our own
 private:
  bool mVisualize;
  GenericVisualization * mVis;
  
  std::vector<int> mChannelIndices;
  int mTriggerChannelIndex;
  double mTriggerThreshold;
  int mLookForwardSamples;
  int mLookBackSamples;
  int mRingBufferSize;
  int mRingBufferCursor;
  GenericSignal * mRingBuffer;
  GenericSignal * mOutput;
  int mSamplesSinceLastTrigger;
  bool mTriggerStateOnPreviousSample;
  double mInputGain;
  double mInputOffset;
  unsigned long mSamplesSeen;
};

#endif // INCLUDED_TrapFilter_H
