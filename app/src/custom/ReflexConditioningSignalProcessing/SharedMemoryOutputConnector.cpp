////////////////////////////////////////////////////////////////////////////////
// $Id: $
// Authors:
// Description: SharedMemoryOutputConnector implementation
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

#include "SharedMemoryOutputConnector.h"
#include "BCIStream.h"


using namespace std;

RegisterFilter( SharedMemoryOutputConnector, 2.H );


SharedMemoryOutputConnector::SharedMemoryOutputConnector()
  : mpShared( NULL )
{

 BEGIN_PARAMETER_DEFINITIONS
   "Connector:Shared%20Memory%20Output%20Connector list   OutputExpressions= 0 % % % % // Leave blank to pass through the signal as normal. Or enter an expression: then the TCP output of this filter will be reduced to just this scalar value.",
   "Connector:Shared%20Memory%20Output%20Connector string SharedMemoryOutput=  % % % % // A file:// or shm:// URL to receive this filter's output  ",
 END_PARAMETER_DEFINITIONS

}


SharedMemoryOutputConnector::~SharedMemoryOutputConnector()
{
  Halt();
}

void
SharedMemoryOutputConnector::Halt()
{
  delete mpShared;
  mpShared = NULL;
  for( unsigned int i = 0; i < mExpressions.size(); i++ )
    delete mExpressions[ i ];
  mExpressions.clear();
}

void
SharedMemoryOutputConnector::Preflight( const SignalProperties & InputProperties, SignalProperties & OutputProperties ) const
{
  // Pre-flight access each state in the list.
  for( int state = 0; state < States->Size(); ++state )
    State( ( *States )[ state ].Name() );

  SharedMemory * shmem = CreateSharedMemory( InputProperties );
  delete shmem;

  ParamRef expressions = Parameter( "OutputExpressions" );
  int nExpressions = expressions->NumValues();
  if( nExpressions )
    OutputProperties = SignalProperties( nExpressions, 1, SignalType::float32 );
  else
    OutputProperties = InputProperties;

  for( int i = 0; i < nExpressions; i++ )
  {
    Expression exp( ( string )expressions( i ) );
    GenericSignal sig( InputProperties );
    exp.Evaluate( &sig );
  }
}

void
SharedMemoryOutputConnector::Initialize( const SignalProperties & InputProperties, const SignalProperties & OutputProperties )
{
  mExpressions.clear();
  ParamRef p = Parameter( "OutputExpressions" );
  for( int i = 0; i < p->NumValues(); i++ )
    mExpressions.push_back( new Expression( ( string )p( i ) ) );
  mpShared = CreateSharedMemory( InputProperties );
}

void
SharedMemoryOutputConnector::StartRun()
{
  if( mpShared ) *reinterpret_cast<unsigned long *>( mpShared->Memory() ) = 0;
}

void
SharedMemoryOutputConnector::Process( const GenericSignal & InputSignal, GenericSignal & OutputSignal )
{
  if( mpShared ) Write( InputSignal, mpShared );
  if( mExpressions.size() == 0 )
    OutputSignal = InputSignal;
  for( unsigned int i = 0; i < mExpressions.size(); i++ )
    OutputSignal( i, 0 ) = mExpressions[ i ]->Evaluate( &InputSignal );
}

std::string
SharedMemoryOutputConnector::StateString() const
{
	string concatenated;
  for( int state = 0; state < States->Size(); state++ )
  {
    if( state ) concatenated += " ";
    concatenated += ( *States )[ state ].Name();
  }
  return concatenated;
}

size_t
SharedMemoryOutputConnector::SharedMemorySize( const SignalProperties & props ) const
{
  string stateString = StateString();
	return sizeof( unsigned long ) * 4 // uint32 count; uint32 channels; uint32 elements; uint32 states;
       + sizeof( double ) * props.Channels() * props.Elements()
			 + sizeof( double ) * States->Size()
			 + sizeof( char ) * ( stateString.length() + 2 ); // add \n and \0 terminator
}

SharedMemory *
SharedMemoryOutputConnector::CreateSharedMemory( const SignalProperties & props ) const
{
  string filename = Parameter( "SharedMemoryOutput" );
  if( filename.length() == 0 ) return NULL; 
  SharedMemory * mm = new SharedMemory( filename, SharedMemorySize( props ) );
  GenericSignal sig( props );
  Write( sig, mm, true );
  return mm;
}

void
SharedMemoryOutputConnector::Write( const GenericSignal & signal, SharedMemory * mm, bool includeStateNames ) const
{
  if( mm == NULL || mm->Memory() == NULL )
  {
    bcierr << "Could not access shared memory" << endl;
    return;
  }
  unsigned long * ulp = reinterpret_cast<unsigned long *>( mm->Memory() );
  unsigned long * pCounter = ulp++;
  *ulp++ = signal.Channels();
  *ulp++ = signal.Elements();
  *ulp++ = States->Size();
  double * dp = reinterpret_cast<double *>( ulp );
  for( int channel = 0; channel < signal.Channels(); channel++ )
    for( int element = 0; element < signal.Elements(); element++ )
      *dp++ = signal( channel, element );
  for( int state = 0; state < States->Size(); state++ )
  {
    const string & name = ( *States )[ state ].Name();
    *dp++ = State( name.c_str() );
  }
  if( includeStateNames )
  {
    char * cp = reinterpret_cast<char *>( dp );
    string stateString = StateString();
    stateString += "\n";  // allows the use of readline()
    strcpy( cp, stateString.c_str() );
    ( *pCounter ) = 0;
  }
  else
    ( *pCounter )++;
}



