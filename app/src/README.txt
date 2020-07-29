This is NOT the complete set of C++ sources required to build the BCI2000 binaries
that EPOCS needs.  Rather, this directory just contains the "custom" additions that
are needed on top of a standard BCI2000 source distro, to build EPOCS' custom
signal-processing module, ReflexConditioningSignalProcessing.

To use these sources:

1.   Use subversion to checkout -r4730 http://bci2000.org/svn/trunk
     At the time of writing (2014-07-31) revisions later than r4730 may have
	 problems compiling.  Unfortunately you will need to use a *different*
	 old revision if you want to rebuild the "cmdline" tools that EPOCS uses
	 (bci_dat2stream, bci_stream2mat and IIRBandpass). For these, you must use r4528.
	 Even more unfortunately, these two goals conflict: r4528 will not allow you to
	 compile the ReflexConditioningSignalProcessing module because the module requires
	 the SharedMemory class that was introduced later; but command-line tools built
	 under r4730 (or indeed any revision from r4530 onwards) will be fatally flawed.
	 Furthermore, r4528 is also the recommended choice if you want to rebuild the
	 Operator or any Signal Source module, because of intermittent freezes and crashes
	 that may occur with binaries built from later revisions.  These problems may or
	 may not be fixed by late 2014.

2.   If using r4528, patch your source distribution using the patch supplied here.

3.   Copy the "custom" directory to your BCI2000 distro, so that it sits at src/custom,
     or just add custom/ReflexConditioningSignalProcessing to your pre-existing src/custom
	 directory if you have one (don't forget to update your src/custom/CMakeLists.txt).
	 
	 Note: instead of copying, it is now possible (on Windows Vista and later) to create
	 symbolic links to directories, using the mklink command. (This may be possible on XP
	 too but you will have to install third-party software.)  This is useful because it
	 means you can continue to version-control the C++ source files here, while
	 simultaneously including them in the BCI2000 build tree.  Note that there are two
	 flavours of link: CMake for Windows will successfully traverse "directory junctions"
	 created with `mklink /j NAME TARGET` but will seemingly NOT work with "directory
	 symbolic links" created with `mklink /d NAME TARGET`. Note also that you may have
	 to run the Command Prompt "as administrator" in order to issue the mklink command.
	 
4.   Build BCI2000 from source, in "Release" mode.  To learn how to do this, see the
     tutorial at http://doc.bci2000.org/Programming_Howto:Quickstart_Guide

