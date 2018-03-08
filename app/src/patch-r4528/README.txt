EPOCS' BCI2000 modules, including the key component, ReflexConditioningSignalProcessing, were compiled
using the source code from subversion repository http://bci2000.org/svn/trunk revision r4528.  Later
versions could not be used because of instabilities in the core framework (these should hopefully be
removed by late 2014).  However, a couple of small features and bugfixes, introduced in later revisions,
were required for EPOCS.  The patch in this directory ports them back into r4528. Start at the top level
of your bci2000 working-copy, and apply the patch (right-click->TortoiseSVN->Apply Patch, then select
the .patch file from this directory).

