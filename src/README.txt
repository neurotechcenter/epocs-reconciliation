This is NOT the complete set of C++ sources required to build the BCI2000 binaries
that EPOCS needs.  Rather, this directory just contains the "custom" additions that
are needed on top of a standard BCI2000 source distro, to build EPOCS' custom
signal-processing module, ReflexConditioningSignalProcessing.

To use these sources:

1.   Use subversion to checkout -r4528 http://bci2000.org/svn/trunk
     At the time of writing (2014-07-31) revisions later than r4528 have a lot of
	 problems, but these might be fixed by late 2014.  If in doubt, stick to r4528.

2.   If using r4528, patch your source distribution using the patch supplied here.

3.   Copy the "custom" directory to your BCI2000 distro, so that it sits at src/custom,
     or just add custom/ReflexConditioningSignalProcessing to your pre-existing src/custom
	 directory if you have one (don't forget to update your src/custom/CMakeLists.txt).
	 
4.   Build BCI2000 from source, in "Release" mode.  To learn how to do this, see the
     tutorial at http://doc.bci2000.org/Programming_Howto:Quickstart_Guide

