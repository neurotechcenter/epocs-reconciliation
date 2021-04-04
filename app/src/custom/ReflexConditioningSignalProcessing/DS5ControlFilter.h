////////////////////////////////////////////////////////////////////////////////
// Authors: 
// Description: DS5ControlFilter header
////////////////////////////////////////////////////////////////////////////////

#ifndef INCLUDED_DS5CONTROLFILTER_H  // makes sure this header is not included more than once
#define INCLUDED_DS5CONTROLFILTER_H

#include "GenericFilter.h"
#include "DS8library.h"

#pragma comment(lib,"DS8library")

class DS5ControlFilter : public GenericFilter
{
 public:
  DS5ControlFilter();
  ~DS5ControlFilter();
  void Publish() override;
  void Preflight( const SignalProperties& Input, SignalProperties& Output ) const override;
  void Initialize( const SignalProperties& Input, const SignalProperties& Output ) override;
  void StartRun() override;
  void Process( const GenericSignal& Input, GenericSignal& Output ) override;
  void StopRun() override;
  void Halt() override;
  bool			enableDS8;
private:
  DS8library::DS8Functions DS8Controller;
};

#endif // INCLUDED_DS5CONTROLFILTER_H
