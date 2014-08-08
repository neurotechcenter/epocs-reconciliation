////////////////////////////////////////////////////////////////////////////////
// $Id: $
// Authors: 
// Description: SharedMemoryOutputConnector header
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

#ifndef INCLUDED_SharedMemoryOutputConnector_H  // makes sure this header is not included more than once
#define INCLUDED_SharedMemoryOutputConnector_H

#include "GenericFilter.h"
#include "Expression.h"
#include "SharedMemory.h"

class SharedMemoryOutputConnector : public GenericFilter
{

 public:
           SharedMemoryOutputConnector();
  virtual ~SharedMemoryOutputConnector();
  virtual void Halt();
  virtual void Preflight( const SignalProperties & InputProperties, SignalProperties & OutputProperties ) const;
  virtual void Initialize( const SignalProperties & InputProperties, const SignalProperties & OutputProperties );
  virtual void StartRun();
  virtual void Process( const GenericSignal & InputSignal, GenericSignal & OutputSignal );
  virtual bool AllowsVisualization() const { return false; }

 private:

  std::string StateString() const;
  size_t SharedMemorySize( const SignalProperties & props ) const;
  SharedMemory * CreateSharedMemory( const SignalProperties & props ) const;
  void Write( const GenericSignal & signal, SharedMemory * mm, bool includeStateNames = false ) const;

  SharedMemory * mpShared;
  std::vector<Expression *> mExpressions;
};

#endif // INCLUDED_SharedMemoryOutputConnector_H
