/*
Welcome to what happens when the funding runs out.

At the time of writing, (April 2014, r4711) BCI2000 framework development has been frozen for some months
with several major bugs.

To compile working versions of BCI2000's command-line filter tools, you need to roll back to r4528 (August
2013), because r4529 does not seem to compile at all and r4530 introduced a bug which corrupts command-line
tool output, making the next tool in the pipeline crash.  For unrelated cmake- and compiler-related reasons,
a version rollback is also required if you want to build anything on osx.

Unfortunately, BackgroundTriggerFilter and RangeIntegrator use a few small utilities and conveniences which
were only introduced into the BCI2000 framework in later versions, so they no longer compile in the rolled-
back framework.  This header adds them back in.

If/when the bug is finally solved, remove this file and revert things by removing any lines that contain the
string Workaround4530 or WORKAROUND4530 in:
	BackgroundTriggerFilter.cpp
	RangeIntegrator.cpp
	CMakeLists.txt
	cmdline/CMakeLists.txt
	
Note that anything that includes WORKAROUND4530 will fail to compile on later framework versions.  I gave up
fiddling to finesse this, and left it this way:

                                                    Compiles on      Compiles on      Compiles on          Compiles on
													WIN32 r4711 ?    WIN32 r4528?     Non-WIN32 r4711?     Non-WIN32 old revision?
													
ReflexConditioningSignalProcessing.exe module           yes               no              no               hopefully              

Command-line tools (RangeIntegrator and friends)        no                yes             no               hopefully

So on WIN32 whatever you do, one or more targets from your solution will fail to build.

*/

#include <string>
#include <cwctype>
#include "StringUtils.h"

using namespace std;

namespace StringUtils
{
    // from StringUtils.cpp r4711
	wstring
	ToUpper( const wstring& s )
	{
	  wstring result = s;
	  for( wstring::iterator i = result.begin(); i != result.end(); ++i )
		*i = ::towupper( *i );
	  return result;
	}

	wstring
	ToLower( const wstring& s )
	{
	  wstring result = s;
	  for( wstring::iterator i = result.begin(); i != result.end(); ++i )
		*i = ::towlower( *i );
	  return result;
	}

    // from StringUtils.h r4711
	inline std::string ToUpper( const std::string& s ) { return ToNarrow( ToUpper( ToWide( s ) ) ); }
    inline std::string ToLower( const std::string& s ) { return ToNarrow( ToLower( ToWide( s ) ) ); }

}

// from Numeric.h r4711
#include <limits>

template<typename T>
const T& Inf( const T& = 0 )
{
  static const T inf = std::numeric_limits<T>::infinity();
  return inf;
}

#include "BCIStream.h"

// #define IN_SECONDS_W4530( x ) Parameter( x ).InSeconds()    // this is what it should be, but it doesn't work in r4528
#define IN_SECONDS_W4530( x ) StringToSeconds( Parameter( x ), Parameter( x ), Parameter( "SampleBlockSize" ), Parameter( "SamplingRate" ) )

double StringToSeconds( std::string stringValue, double numericValue, double samplesPerBlock, double samplesPerSecond )
{
	double gain;
	string reversed;
	unsigned int len = stringValue.size();
	for( unsigned int i = 0; i < len; i++ )
		reversed += stringValue[ len - i - 1 ];
	const char * rev = reversed.c_str();
	if(      ::strncmp( rev, "sm", 2 ) == 0 && !::isalpha( rev[ 2 ] ) ) gain = 0.001;
	else if( ::strncmp( rev, "s",  1 ) == 0 && !::isalpha( rev[ 1 ] ) ) gain = 1.0;
	else if( isalpha( rev[ 0 ] ) ) bcierr << "Truly unexpected measurement unit in expression \"" << stringValue << "\"" << endl;
	else gain = samplesPerBlock / samplesPerSecond;
	return numericValue * gain;
}

// #define IN_VOLTS_W4530( x ) Parameter( x ).InVolts()    // this is what it should be, but it doesn't work in r4528
#define IN_VOLTS_W4530( x ) StringToVolts( Parameter( x ), Parameter( x ) )

double StringToVolts( std::string stringValue, double numericValue )
{
	double gain;
	string reversed;
	unsigned int len = stringValue.size();
	for( unsigned int i = 0; i < len; i++ )
		reversed += stringValue[ len - i - 1 ];
	const char * rev = reversed.c_str();
	if(      ::strncmp( rev, "Vum", 3 ) == 0 && !::isalpha( rev[ 3 ] ) ) gain = 0.000001;
	else if( ::strncmp( rev, "Vu",  2 ) == 0 && !::isalpha( rev[ 2 ] ) ) gain = 0.000001;
	else if( ::strncmp( rev, "Vm",  2 ) == 0 && !::isalpha( rev[ 2 ] ) ) gain = 0.001;
	else if( ::strncmp( rev, "V",   1 ) == 0 && !::isalpha( rev[ 1 ] ) ) gain = 1.0;
	else if( isalpha( rev[ 0 ] ) ) bcierr << "Truly unexpected measurement unit in expression \"" << stringValue << "\"" << endl;
	else gain = 0.000001;
	return numericValue * gain;
}
