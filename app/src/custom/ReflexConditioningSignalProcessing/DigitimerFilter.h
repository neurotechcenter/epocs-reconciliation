////////////////////////////////////////////////////////////////////////////////
// Authors: 
// Description: DigitimerFilter header
////////////////////////////////////////////////////////////////////////////////

#ifndef INCLUDED_DIGITIMERFILTER_H  // makes sure this header is not included more than once
#define INCLUDED_DIGITIMERFILTER_H

#include "GenericFilter.h"
#include "D188Library.h"
#include "DS8Library.h"
#include "windows.h"
#include "winbase.h"

#pragma comment(lib,"DS8library")

class DigitimerFilter : public GenericFilter
{
 public:
  DigitimerFilter();
  ~DigitimerFilter();
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
  bool	enableDS8;
 private:
  int nD188;
  D188library::D188Functions D188Controller;
  DS8library::DS8Functions DS8Controller;

};

#endif // INCLUDED_DIGITIMERFILTER_H