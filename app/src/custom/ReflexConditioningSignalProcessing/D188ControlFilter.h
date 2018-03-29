////////////////////////////////////////////////////////////////////////////////
// Authors: 
// Description: D188ControlFilter header
////////////////////////////////////////////////////////////////////////////////

#ifndef INCLUDED_D188CONTROLFILTER_H  // makes sure this header is not included more than once
#define INCLUDED_D188CONTROLFILTER_H

#include "GenericFilter.h"
#include "NIDAQmx.imports.h"

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
 private:
	int    ReportError(int errCode) const; 
	int	   ParseMatrix(
		std::string		    & DigitalDeviceName,
		std::string			& AnalogPortSpec,
		std::string			& DigitalPortSpec) const;
};

#endif // INCLUDED_D188CONTROLFILTER_H
