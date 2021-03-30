////////////////////////////////////////////////////////////////////////////////
// $Id: $
// Authors: 
// Description: RangeIntegrator header
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

#ifndef INCLUDED_RangeIntegrator_H  // makes sure this header is not included more than once
#define INCLUDED_RangeIntegrator_H

#include "GenericFilter.h"

class RangeIntegrator : public GenericFilter
{
 public:
           RangeIntegrator();
  virtual ~RangeIntegrator();
  virtual void Publish();
  virtual void Halt();
  virtual void Preflight(  const SignalProperties& Input,       SignalProperties& Output ) const;
  virtual void Initialize( const SignalProperties& Input, const SignalProperties& Output );
  virtual void StartRun();
  virtual void Process(    const GenericSignal&    Input,       GenericSignal&    Output );

 private:
  std::vector<int>    mInputChannelIndices;
  std::vector<int>    mStartSamples;
  std::vector<int>    mStopSamples;
  std::vector<bool>   mSubtractMeanFlags;
  std::vector<double> mNorms;
  std::vector<double> mWeights;
  std::vector<int>    mResponseChannelIndices;
  std::vector<int>    mAssessmentIndices;
  std::vector<double> mMinValues;
  std::vector<double> mMaxValues;
  std::vector<double> mFeedbackWeights;
  std::vector<int>    mRefAssessmentIndices;
  std::vector<double> mRefFeedbackWeights;
  SignalProperties    mResponseProperties;
  bool                mComputeMeans;
  bool                mPassThrough;
  double              mInputGain;
  double              mInputOffset;
  int                 mTrialsCompleted;
  int				  mAnalysisType;
  void ParseMatrices(

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
	std::vector<int>    & refassessmentIndices,
	std::vector<double> & reffeedbackWeights,

    const SignalProperties &  InputProperties,
    SignalProperties &  responseProperties

  ) const;
  
};

#endif // INCLUDED_RangeIntegrator_H
