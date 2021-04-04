////////////////////////////////////////////////////////////////////////////////
// Authors: 
// Description: D188ControlFilter header
////////////////////////////////////////////////////////////////////////////////

#ifndef INCLUDED_D188CONTROLFILTER_H  // makes sure this header is not included more than once
#define INCLUDED_D188CONTROLFILTER_H

#include "GenericFilter.h"
#include "D188Library.h"
#include "windows.h"
#include "winbase.h"

class D188ControlFilter : public GenericFilter
{
 public:
  D188ControlFilter();
  ~D188ControlFilter();
  void Publish() override;
  void Preflight( const SignalProperties& Input, SignalProperties& Output ) const override;
  void Initialize( const SignalProperties& Input, const SignalProperties& Output ) override;
  void StartRun() override;
  void Process( const GenericSignal& Input, GenericSignal& Output ) override;
  void StopRun() override;
  void Halt() override;
  //Load Library
  bool iD188;
  int Channel;
 private:
  int nD188;
  D188library::D188Functions D188Controller;
};

#endif // INCLUDED_D188CONTROLFILTER_H
