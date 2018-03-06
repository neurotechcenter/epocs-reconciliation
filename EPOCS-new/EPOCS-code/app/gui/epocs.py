"""
This is a graphical user interface (GUI) implementation for the evoked potential operant
conditioning system (EPOCS). This Python 2.x code uses the built-in Tkinter toolkit for
organizing and rendering GUI elements, and the third-party matplotlib package for rendering
graphs and other custom graphics.  Under the hood, the EPOCS GUI calls BCI2000 binaries.
BCI2000 does most of the actual real-time processing and saves the data file, but this GUI
replaces the BCI2000 Operator window and config dialog by propviding an interface for the
therapist/researcher to configure, start and stop runs; it also replaces the BCI2000
Application module by providing real-time biofeedback to the patient/subject; finally it
provides specialized offline analysis of the most recently collected data.

This file may be run as a standalone python file.  It may take the following optional
command-line arguments:

--custom=XXX : specify a path XXX to a custom batch file, relative to the current (gui or
               gui-bin) directory.  For example,  --custom=../custom/VisualizeSource.bat
               The specified file will be interpreted by the BCI2000 scripting engine
               and run when BCI2000 has launched (see the web documentation on "BCI2000
               operator module scripting"). The custom script can be used to add custom
               parameters and state variables, and set parameter values---for example,
               to open BCI2000 visualization windows and to increase the number of
               acquired channels.  The best place to add a --custom switch is in the
               "Target" line in the properties of the shortcut you use to launch EPOCS.

--offline    : start in "offline analysis" mode (perform analysis on old files) instead of
               the default "online" mode.

--devel      : start in "development" mode:  use the BCI2000 FilePlayback module as source
               instead of the live data acquisition module, and include a "Load Demo Data"
               button in some modes so that the "Analysis" buttons can be pressed immediately
               without having to wait to gather data. Internally, the --devel flag causes
               the global variable DEVEL to be set to True.   The application also starts in
               development mode automatically if no interface to the acquisition hardware
               API can be found at the time of launch.

--debug      : start in "debug" mode:  this is usually but not always used in conjunction
               with --devel.  It causes the global variable DEBUG to be set to True.  This
               contingency may be used to trigger behavior that is useful in debugging but
               which might not normally occur (for example, it was useful in debugging a
               problem with the StickySpanSelector in the Voluntary Contraction analysis
               window, which would prevent zooming when its value was set to some values
               but not others:   if DEBUG==True: set_to_problematic_values()   )

Notes Amir Eftekhar May/June 2016 - Added functionality -
                M-wave window: A window that allows the user to see analysis of the M-Wave, including
                Rectified amplitude, the mean for that set of trials and also to display the mean.
                Where additions are made they are noted with ###AMIR + DESC

                TODO:
"""




"""
TODO

    better ExampleData for all modes
    --offline plotting of a VC file seems to crash (perhaps only if there happened to be triggers in the file?)

    caveats and gotchas:
        BackgroundTriggerFilter.cpp issue: assuming background is in range, time between triggers actually
        seems to come out to MinTimeBetweenTriggers + 1 sample block

    nice-to-haves:
        NIDAQmxADC: acquisition of floating-point raw data instead of integers

        NIDAQFilter: reparameterize to remove reliance on command-line parameters

        make separate settings entry to govern maximum random extra hold duration?  (if so: remember to enforce its rounding to whole number of segments)

        offline analysis
            make progress-when-reading / logged-results prettier (esp. in py2exe version)?
            related issue: make log-file go somewhere saveable other than just clipboard?
            clipboard gets wiped on quit (see http://stackoverflow.com/questions/579687 ) - NB: problem seems to go away in py2exe'd version

            maybe override ResponseInterval from .dat file with ResponseInterval from -LastSettings-Offline.txt config file?
                (but not with the setting from the online one, if present)
            (semi-)automatic removal of individual trials? using new outlier-removal tab?
            button for saving figures as pdf?
"""

import Tkinter as tkinter
import inspect
import mmap
import os
import re
import struct
import sys

import matplotlib.pyplot   # this is the online GUI's only non-bundled third-party dependency besides Python itself (although implicitly, matplotlib in turn also requires numpy)

tksuperclass = tkinter.Tk
import imp
try: import ttk
except ImportError: import Tix; tksuperclass = Tix.Tk  # ...because Python 2.5 does not have ttk. Included for legacy compatibility:  this GUI was originally developed under Python 2.5.4 without ttk, but has now transitioned to Python 2.7.5 with ttk

import ctypes
try: ctypes.windll.nicaiu
except: DEVEL = True    # automatically pop into DEVEL mode (using FilePlayback instead of live signal recording) if no NIDAQmx interface found on this computer
else:   DEVEL = False   # otherwise, DEVEL mode will only be activated if you have started EPOCS with the --devel command-line switch

DEBUG = False  # if set to true with the --debug command-line switch, print debug/version info to the system log (even if we're not in FilePlayback mode)
CUSTOM = ''    # BCI2000 script file to run (set with command-line switch --custom=foo.bat )

GUIDIR = os.path.dirname( os.path.realpath( inspect.getfile( inspect.currentframe() ) ) ) # GUIDIR is the directory where this executable lives - will also be expected to contain .ico file and .ini files
BCI2000LAUNCHDIR = os.path.abspath( os.path.join( GUIDIR, '../prog' ) ) # BCI2000LAUNCHDIR contains the BCI2000 binaries: it is expected to be in ../prog relative to this python file
if not os.path.isfile( os.path.join( BCI2000LAUNCHDIR, 'BCI2000Remote.py' ) ): raise ImportError( 'could not find the prog directory containing BCI2000Remote.py' )
if BCI2000LAUNCHDIR not in sys.path: sys.path.append( BCI2000LAUNCHDIR )
import BCI2000Remote
from DependantClasses import TK; TkMPL = TK.TkMPL

try:
    from DependantClasses.MwaveAnalysisClass import MWaveAnalysisWindow as MWaveAnalysisWindow
except:
    pass

from DependantClasses.DS5LibClass import DS5LibClass as DS5LibClass

try:
    from DependantClasses import CurrentControl as CurrentControl
except:
    pass

EPOCSVERSION = 1.1
EPOCSVERSIONDATE = "3-6-18"

#del spam, spam_info
#This calls CoreFunctions so no need to do import it
from DependantClasses.CoreGUIcomponents import *
#
# def LoadPackages(parent):
#
#     import tkMessageBox
#
#     # Load StimGUI if package installed
#     try:
#         spam_info = imp.find_module('DependantClasses')
#         spam = imp.load_module('DependantClasses',*spam_info)
#         imp.find_module('CurrentControl',spam.__path__)
#         del spam, spam_info
#         found = True
#     except:
#         found = False
#         tkMessageBox.showinfo('Packages','Packages not found!')
#
#     if found:
#         from DependantClasses import CurrentControl as CurrentControl
#         parent.stimGUI = CurrentControl.CurrentControlWindow(parent=parent)


class Operator( object ):
    """
    One Operator instance coordinates communication between one GUI instance and BCI2000's binaries.  It loads, updates and saves default
    settings, translates these two and from BCI2000 parameter format, sends them to and receives them from the BCI2000 Operator module,
    and receives signal information from the BCI2000 ReflexConditioningSignalProcessing module via a shared-memory mechanism.  It also
    manages the session's settings, loading them from and saving them to disk in a subject- and session- specific way so that each
    subject's sessions can pick up where they left off last.

    An Operator() instance is created during construction of a GUI() instance and stored as that GUI's self.operator attribute.

    The OfflineAnalysis() class tries to fool other classes into thinking it is a GUI(), and therefore also performs
    self.operator = Operator() during construction. In this case, however, the Operator is never actually told to launch or talk to
    BCI2000, but rather just handles the process of loading and saving subject-specific analysis settings.
    """
    def __init__( self ):

        self.dateFormat = '%Y-%m-%d-%H-%M'
        self.sessionStamp = None
        self.needSetConfig = True
        self.started = False

        self.mmfilename = 'epocs.mmap'
        self.mmfile = None
        self.mm = None

        dataDir = '../../data'

        self.params = Bunch(   # keys without underscores are direct representations of BCI2000 parameters
                               # keys starting with an underscore may not share a name with a BCI2000 parameter exactly, and may require translation into BCI2000 parameter values
            SubjectName = '',
            SessionStamp = time.strftime( self.dateFormat, time.localtime( 0 ) ),
            SubjectRun = '00',
            DataDirectory = dataDir,
            FileFormat = 'dat',
            DataFile = '${SubjectName}/${SubjectName}-${SessionStamp}/${SubjectName}-${SessionStamp}-R${SubjectRun}-${ApplicationMode}.${FileFormat}',
            ApplicationMode = 'ST',
            TriggerExpression = '',

            BackgroundSegmentDuration = '200ms',
            LookForward = '500ms',
            LookBack = '100ms',

            _FeedbackChannel =       'EMG1',
            _ResponseChannel =       'EMG1',
            _EMGChannelNames =       [ 'EMG1', 'EMG2', ],  # "parameter" names beginning with '_' are not real BCI2000 parameters
            _BackgroundMin =         [     5,      0,  ],  # and will not be sent to BCI2000 automatically. Rather, the appropriate
            _BackgroundMax =         [    18,     15,  ],  # matrix parameters will be constructed from them in SendConditioningParameters()

            _ResponseStartMsec =     [    14,     14,  ],
            _ResponseEndMsec =       [    30,     30,  ],

            _ComparisonStartMsec =   [    4,      4,   ],
            _ComparisonEndMsec =     [    13,     13,  ],
            _PrestimulusStartMsec =  [   -52,    -52,  ],
            _PrestimulusEndMsec =    [    -2,     -2,  ],

            _ResponseMin =           [    10,      0,  ],
            _ResponseMax =           [  None,   None,  ],

            _TraceLimitVolts =       [  0.010,  0.010  ],

            _TargetPercentile =      66,

            _BaselineResponse = None,
            _ResponseBarLimit = 50,
            _VCBackgroundBarLimit = 200,
            _EarlyLoggedCTBaselines = {},

            _VoltageUnits = 'mV',  # as what unit should we interpret _BackgroundMin, _BackgroundMax, _ResponseMin, _ResponseMax, _ResponseBarLimit and _VCBackgroundBarLimit

            _SecondsBetweenTriggers = 5,
            _SecondsBetweenStimulusTests = 3,
            _BarUpdatePeriodMsec = 200,
            _BackgroundHoldSec = 2,       # should be an integer multiple of BackgroundSegmentDuration
            _BackgroundHoldExtraSec = 0,  # should be an integer multiple of BackgroundSegmentDuration

            _ctTrialsCount = 75,
            _ttTrialsCount = 75,
            _UpDownTrialCount = 'up',
            _MwaveOverlay = [30, 20],
            _IncrementStart = 0.5,
            _IncrementIncrement=0.25,
            _CurrentLimit=50,
            _DigitimerEnable='on',
            _DigitimerSelect='DS8',
        )
        self.remote = None

    def Launch( self ):
        """
        To be called once during GUI initialization: launches BCI2000 by invoking its batch file.
        """
        self.remote = BCI2000Remote.BCI2000Remote()
        self.remote.Connect()
        # the command-line args to the .bat file are:
        #  (1) "master" or "slave"  (the default, "master", would mean use BCI2000 standalone with no EPOCS GUI, so we will always be saying "slave" here)
        #  (2) "replay" or "live"   (in DEVEL mode, i.e. when epocs.py is run with the --devel option, we replay data from a sample file using BCI2000's FilePlayback module; otherwise, and by default, we record live from the data acquisition board)
        #  (3) optionally the path to a CUSTOM script (specified as a command-line option to epocs.py such as --custom=../custom/whatever.bat)
        if DEVEL: self.bci2000( 'execute script ../batch/run-nidaqmx.bat slave replay ' + CUSTOM )
        else:     self.bci2000( 'execute script ../batch/run-nidaqmx.bat slave live   ' + CUSTOM )
        self.Set( TriggerExpression=self.remote.GetParameter( 'TriggerExpression' ) )
        # We will be setting TriggerExpression to '0' to disable triggers in VC mode, and then setting it back to whatever it was before for other modes (either '', or whatever value has been set by the CUSTOM script). Therefore, we query its initial value here.

    def DataRoot( self ):
        """
        Return the absolute path to the top-level data directory, determined by self.params.DataDirectory
        """
        return ResolveDirectory( self.params.DataDirectory, BCI2000LAUNCHDIR )

    def Subjects( self ):
        """
        Return a list of subject identifiers (the name of any subdirectory of the DataRoot() directory
        is assumed to denote a subject if that subdirectory contains a subject settings file)
        """
        dataRoot = self.DataRoot()
        if not os.path.isdir( dataRoot ): return []
        return [ x for x in os.listdir( dataRoot ) if os.path.isfile( self.SubjectSettingsFile( x ) ) ]

    def SubjectSettingsFile( self, subjectName=None, suffix='' ):
        """
        Return the absolute path to a file, which may or may not yet exist, in which to store the default
        settings for the current (or explicitly named) subject.  The file will be located at
           $DATAROOT/$SUBJECTID/$SUBJECTID-LastSettings.txt
        where $DATAROOT can be obtained by the DataRoot() method and $SUBJECTID is the subject identifier
        (either the <subjectName> argument to this method if specified, or self.params.SubjectName if not).
        There may also be an optional <suffix> between '-LastSettings' and '.txt'
        Subject settings files are a convenience only, to remember settings from one session to the next
        - it is no great disaster if they are deleted, because each data file itself contains a complete
        specification of the settings at the time of recording).

        Called by ReadSubjectSettings() and WriteSubjectSettings()
        """
        if subjectName == None: subjectName = self.params.SubjectName
        if not subjectName: return ''
        return os.path.join( self.DataRoot(), subjectName, subjectName + '-LastSettings' + suffix + '.txt' )

    def ReadSubjectSettings( self, subjectName=None, suffix='' ):
        """
        Use ReadDict() to read the SubjectSettingsFile() corresponding to the specified <subjectName>
        (or self.params.SubjectName if not specified) and <suffix>. Return the result as a dict.

        Called by LoadSubjectSettings(), LastSessionStamp(), and the OfflineAnalysis class
        """
        if subjectName == None: subjectName = self.params.SubjectName
        filename = self.SubjectSettingsFile( subjectName, suffix=suffix )
        if not os.path.isfile( filename ): return { 'SubjectName': subjectName }
        return ReadDict( filename )

    def LoadSubjectSettings( self, subjectName=None, newSession=False, suffix='' ):
        """
        Use ReadSubjectSettings() to read the specified (or current) subject's last settings, and adopt
        these settings by updating self.params with them.

        Called by NewSession() and ContinueSession()
        """
        self.Set( **self.ReadSubjectSettings( subjectName, suffix=suffix ) )
        if newSession: self.Set( SessionStamp=time.time() )

    def WriteSubjectSettings( self, subjectName=None, suffix='' ):
        """
        Use WriteDict() to save a SubjectSettingsFile() for the specified (or current) subject.
        Note that only the SubjectName, SessionStamp, and underscored parameters are saved.

        Called during SetConfig(), and also when either the online GUI() or the OfflineAnalysis window shuts down (note
        that the latter uses a different suffix to keep its settings separate from the online settings).
        """
        d = dict( ( k, v ) for k, v in self.params.items() if k in 'SubjectName SessionStamp'.split() or k.startswith( '_' ) )
        WriteDict( d, self.SubjectSettingsFile( subjectName=subjectName, suffix=suffix ) )

    def LastSessionStamp( self, subjectName=None ):
        """
        Use ReadSubjectSettings() to find out the date and time that the specified (or current) subject's last session started.

        Called by the online GUI when presenting an interface for specifying a subject name, and also by the OfflineAnalysis object.
        """
        if subjectName == None: subjectName = self.params.SubjectName
        record = self.ReadSubjectSettings( subjectName )
        try: return time.mktime( time.strptime( record[ 'SessionStamp' ], self.dateFormat ) )
        except: return 0

    def GetVolts( self, value ):
        """
        Assuming <value> is expressed in the default voltage units stored in self.params._VoltageUnits, return the
        corresponding value in Volts. Called in many places.  Uses the global GetVolts() function.
        """
        return GetVolts( value, self.params._VoltageUnits )

    def FriendlyDate( self, stamp=None ):
        """
        Convert a serial date number (in seconds since the POSIX epoch) into
        a human-readable ISO date string suitable for datestamping a session
        (precision only down as far as minutes).  <stamp> defaults to the
        start time of the current session if not specified.
        """
        if stamp == None: stamp = self.sessionStamp
        return time.strftime( '%Y-%m-%d  %H:%M', time.localtime( stamp ) )

    def LastRunNumber( self, mode='' ):
        """
        Return the run number of the last file recorded in the current DataDirectory().
        If <mode> is specified as a two-letter code (e.g. 'VC', 'RC', etc), return
        the run number of the last file recorded in the specified mode.
        """
        d = self.DataDirectory()
        if not os.path.isdir( d ): return 0
        runs = [ self.RunNumber( x ) for x in os.listdir( d ) if x.lower().endswith( ( mode + '.' + self.params.FileFormat ).lower() ) ]
        if len( runs ) == 0: return 0
        return max( runs )

    def NextRunNumber( self ):
        """
        Return the run number that will be used for the next recording, based on the files that are currently
        in the DataDirectory().

        Called during SetConfig() and Start()
        """
        return self.LastRunNumber() + 1  # let the numbering be global - look for the last run number in *any* mode

    def RunNumber( self, datfilename ):
        """
        Extract the run number from a file name.

        Called by LastRunNumber()
        """
        parentdir, datfile = os.path.split( datfilename )
        stem, ext = os.path.splitext( datfilename )
        stem = '-' + '-'.join( stem.split( '-' )[ 1: ] ) + '-'
        m = re.match( '.*-R([0-9]+)-.*', stem )
        if m == None: return None
        return int( m.groups()[ 0 ] )

    def DataDirectory( self ):
        """
        Return the absolute path to the directory in which data files will be recorded for the current
        subject and session.    This function interprets self.params.DataDirectory and self.params.DataFile
        in the same way that BCI2000 itself interprets the corresponding DataDirectory and DataFile parameters
        (NB: BCI2000's DataDirectory parameter specifies the top-level non-subject-specific directory which
        we prefer to call DataRoot() here in the Python code, whereas BCI2000's DataFile parameter specifies
        the subject-specific subdirectory of the data root as well as the name of the data file itself).
        """
        s = '${DataDirectory}/' + self.params.DataFile
        for k, v in self.params.items():
            match = '${%s}' % k
            if match in s: s = s.replace( match, str( v ) )
        d = os.path.split( s )[ 0 ]
        return ResolveDirectory( d, BCI2000LAUNCHDIR )

    def LogFile( self, autoCreate=False ):
        """
        Return the absolute path to the log file for the current subject and session.
        With autoCreate=True, the file will be created and initialized if it does not already exist.
        """
        logfile = os.path.join( self.DataDirectory(), '%s-%s-log.txt' % ( self.params.SubjectName, self.params.SessionStamp ) )
        if autoCreate and not os.path.isfile( logfile ):
            f = open( MakeWayFor( logfile ), 'at' )
            # Add EPOCS version number here
            f.write('EPOCS version: %s (date: %s)\n' % (str(EPOCSVERSION), str(EPOCSVERSIONDATE)))
            f.write( 'Patient Code: %s\nSession Code: %s\n' % ( self.params.SubjectName, self.params.SessionStamp ) )
            f.close()
        return logfile

    def Set( self, **kwargs ):
        """
        Set one or more members of self.params (remember, names without an underscore will be sent directly
        to BCI2000 as parameters, whereas names beginning with underscores may be processed in SendConditioningParameters
        and translated into BCI2000 parameters). Example:
            Set( Spam=3, Eggs='eggs' )
        """
        container = self.params
        for key, value in kwargs.items():
            #flush( repr( key ) + ' : ' + repr( value ) )
            old = getattr( container, key, None )
            if key == 'SubjectName':
                cleaned = ''.join( c for c in value if c.lower() in 'abcdefghijklmnopqrstuvwxyz0123456789' )
                if cleaned == '': raise ValueError( 'invalid subject name "%s"' % value )
                else: value = cleaned
            if key == 'SessionStamp':
                if isinstance( value, ( int, float ) ): value = time.strftime( self.dateFormat, time.localtime( value ) )
            if value != old:
                if self.started: raise RuntimeError( "must call Stop() method first" )
                self.needSetConfig = True
            setattr( container, key, value )
            if key == 'SessionStamp':
                self.sessionStamp = time.mktime( time.strptime( value, self.dateFormat ) )

    def bci2000( self, cmd ):
        """
        Send a command to the BCI2000 command interpreter.
        """
        #flush( cmd )
        #os.system( os.path.join( '..', '..', '..', 'prog', 'BCI2000Shell' ) + ' -c ' + cmd )   # old style, via BCI2000Shell binary
        return self.remote.Execute( cmd )  # new style, via BCI2000Remote.BCI2000Remote object

    def SendParameter( self, key, value=None ):
        """
        Send the specified parameter (name specified as <key>) to BCI2000 and set its value.
        If no <value> is specified, the current value of self.params[ key ] is used.

        Either way, SendParameter will escape the value for you according to BCI2000's
        requirements (i.e. turn empty strings into '%', or replace spaces with '%20').

        Called by SendConditioningParameters() and SetConfig().
        """
        if value == None: value = self.params[ key ]
        value = str( value )
        for ch in '% ${}': value = value.replace( ch, '%%%02x' % ord(ch) )
        if value == '': value = '%'
        self.bci2000( 'set parameter %s %s' % ( key, value ) )

    def SendConditioningParameters( self ):
        """
        Some of the required BCI2000 parameters have relatively complicated structure
        (e.g. matrices of mixed content type). This method, called during SetConfig(),
        compiles, converts and translates EPOCS settings (members of self.params whose
        names begin with an underscore) into BCI2000 parameters and sends them to
        BCI2000 either using SendParameter() for the simple cases, or directly using
        bci2000() for lists and matrices.
        """
        channelNames = [ x.replace( ' ', '%20' ) for x in self.params._EMGChannelNames ] # TODO: for now, we'll have to assume that these names are correctly configured in the parameter file

        def stringify_voltages( listOfVoltages ):
            out = []
            for x in listOfVoltages:
                if x == None: out.append( '%' )
                else: out.append( '%g%s' % ( x, self.params._VoltageUnits ) )
            return out

        minV, maxV = stringify_voltages( self.params._BackgroundMin ), stringify_voltages( self.params._BackgroundMax )
        if self.params.ApplicationMode.lower() in [ 'vc' ]:
            minV, maxV = [ '%' for x in minV ], [ '%' for x in maxV ]

        fbChannel = self.params._FeedbackChannel
        cols =   'Input%20Channel   Subtract%20Mean?   Norm    Min%20Amplitude     Max%20Amplitude    Feedback%20Weight'
        rows = [ '      %s                 yes           1          %s                  %s                   %g        '  %
                 (     name,                                      minV[ i ],         maxV[ i ],       name == fbChannel ) for i, name in enumerate( channelNames ) ]
        self.bci2000( 'set parameter Background matrix BackgroundChannels= ' + str( len( rows ) ) + ' { ' + cols + ' } ' + ' '.join( rows ) )

        start, end = self.params._ResponseStartMsec, self.params._ResponseEndMsec
        start2, end2 = self.params._ComparisonStartMsec, self.params._ComparisonEndMsec #NEW
        cols =   'Input%20Channel   Start        End   Subtract%20Mean?   Norm    Weight   Response%20Name'
        rows = [ '    %s            %gms        %gms         no             1       1.0          %s       ' %
                 (    name,      start[ i ],  end[ i ],                                      name,        ) for i, name in enumerate( channelNames ) ]
        rows.extend(['    %s            %gms        %gms         no             1       1.0          %s  ' %#NEW
                     (name, 		start2[0], end2[0], 										name + 'a')  for i, name in enumerate( channelNames )])
        self.bci2000( 'set parameter Responses  matrix ResponseDefinition= ' + str( len( rows ) ) + ' { ' + cols + ' } ' + ' '.join( rows ) )

        minV, maxV = stringify_voltages( self.params._ResponseMin ), stringify_voltages( self.params._ResponseMax )
        cols =   'Response%20Name     Min%20Amplitude      Max%20Amplitude    Feedback%20Weight'
        rows = [ '     %s                  %s                  %s                    %g        ' %
                 (    name,              minV[ i ],         maxV[ i ],             i == 0      ) for i, name in enumerate( channelNames ) ]
        self.bci2000( 'set parameter Responses  matrix ResponseAssessment= ' + str( len( rows ) ) + ' { ' + cols + ' } ' + ' '.join( rows ) )

        cols = 'Response%20Name    Feedback%20Weight'
        rows = ['     %s                  %g        ' %
                (name+'a', 				    i == 0) for i, name in enumerate(channelNames)]
        self.bci2000(
            'set parameter Responses  matrix ReferenceAssessment= ' + str(len(rows)) + ' { ' + cols + ' } ' + ' '.join(
                rows))

        secondsPerSegment = float( self.params.BackgroundSegmentDuration.strip( 'ms' ) ) / 1000.0
        if self.params.ApplicationMode.lower() in [ 'st' ]:
            self.SendParameter( 'MinTimeBetweenTriggers', '%gs' % self.params._SecondsBetweenStimulusTests )
            self.SendParameter( 'BackgroundHoldDuration', 0 )
            self.SendParameter( 'MaxRandomExtraHoldDuration', 0 )
        else:
            self.SendParameter( 'MinTimeBetweenTriggers', '%gs' % self.params._SecondsBetweenTriggers )
            self.SendParameter( 'BackgroundHoldDuration', '%gs' % self.params._BackgroundHoldSec )
            self.SendParameter( 'MaxRandomExtraHoldDuration', '%gs' % self.params._BackgroundHoldExtraSec )
        if self.params.ApplicationMode.lower() in [ 'vc' ]: self.SendParameter( 'TriggerExpression', 0 )
        else:                                               self.SendParameter( 'TriggerExpression' )
        self.SendParameter( 'FeedbackTimeConstant', '%gms' % self.params._BarUpdatePeriodMsec )

        bgLimit, rLimit, rBaseline = stringify_voltages( [ self.GetBackgroundBarLimit( self.params.ApplicationMode ), self.params._ResponseBarLimit, self.params._BaselineResponse ] )

        self.SendParameter( 'BackgroundScaleLimit',  bgLimit )
        self.SendParameter( 'ResponseScaleLimit',    rLimit )
        self.SendParameter( 'BaselineResponseLevel', rBaseline )

    def GetBackgroundBarTarget( self ):
        """
        TODO
        """
        channelIndex = self.params._EMGChannelNames.index( self.params._FeedbackChannel )
        lower, upper = self.params._BackgroundMin[ channelIndex ], self.params._BackgroundMax[ channelIndex ]
        return lower, upper

    def GetResponseBarTarget( self ):
        """
        TODO
        """
        channelIndex = self.params._EMGChannelNames.index( self.params._ResponseChannel )
        lower, upper = self.params._ResponseMin[ channelIndex ], self.params._ResponseMax[ channelIndex ]
        return lower, upper

    def GetBackgroundBarLimit( self, mode ):
        """
        Determine the upper y-axis limit on the graph in which the ongoing background
        EMG level is displayed. VC mode has its own separate setting for this.  In
        other modes, if both a minimum and maximum limit have been specified (i.e.
        self.params._BackgroundMin[i] and self.params._BackgroundMax[i], where i is the
        channel being used for continuous feedback) then ensure that that range is
        centered vertically in the middle of the graph. If only one limit has been set,
        ensure that that limit is centered.
        """
        mode = mode.lower()
        lower, upper = self.GetBackgroundBarTarget()
        if lower == 0: lower = None
        if mode in [ 'vc' ]: return self.params._VCBackgroundBarLimit
        elif lower == None and upper == None: return self.params._VCBackgroundBarLimit
        elif lower == None and upper != None: return upper * 2.0
        elif lower != None and upper == None: return lower * 2.0
        else: return lower + upper

    def SetConfig( self, work_around_bci2000_bug=False ):
        """
        Update parameters ready for the next run, transfer them to BCI2000, call
        WriteSubjectSettings(), and issue a SETCONFIG command to BCI2000 (i.e.
        virtually press its "Set Config" button).

        NB:  because of a bug in BCI2000, documented at
        http://bci2000.org/tracproj/ticket/131 , one should not issue a SETCONFIG command
        without then starting a run:  if you do, BCI2000 may ignore future SET PARAMETER
        updates you might need to perform before actually starting the run.  In EPOCS, this is
        only a problem the *first* time SetConfig() is called, immediately after Launch().
        At all other times SetConfig() will only be called immediately before starting a run.
        To cope with this, we pass work_around_bci2000_bug=True in the former case: then,
        parameters are updated but the setconfig command is not actually issued. This has the
        minor disadvantage that any BCI2000 misconfiguration will not become obvious immediately
        on launch, but only when EPOCS's "Start" button is pressed for the first time.
        """
        self.params.SubjectRun = '%02d' % self.NextRunNumber()
        for p in self.params:
            if not p.startswith( '_' ): self.SendParameter( p )

        self.SendConditioningParameters()
        if self.mmfilename:
            self.mmfileURL = 'file://' + ( self.mmfilename ).replace( '\\', '/' )
            self.SendParameter( 'SharedMemoryOutput', self.mmfileURL )
            self.bci2000( 'set parameter Connector list OutputExpressions= 2 BackgroundFeedbackValue ResponseFeedbackValue' )
        else:
            self.bci2000( 'set parameter Connector list OutputExpressions= 0' )

        if not work_around_bci2000_bug:
            self.bci2000( 'wait for Connected|ParamsModified 5' )
            self.bci2000( 'setconfig' )
            self.needSetConfig = False
        self.WriteSubjectSettings()


    def Stop( self ):
        """
        Tell BCI2000 to stop the currently ongoing run, if any, and stop listening for
        input on the SharedMemory connection.
        """
        if self.mm:
            self.mmlock.acquire()
            self.mm = None
            self.mmfile.close()
            self.mmlock.release()
        self.bci2000( 'set state Running 0' )
        self.started = False

    def Start( self, mode=None ):
        """
        Tell BCI2000 to start a new run.  If this involves a different mode or
        different parameters than the last run (the latter being detected by the
        fact that self.needSetConfig is set to True), then call SetConfig() first.
        At the same time, create, open and initialize the memory-mapped file for
        inter-process communication (see ReadMM() below).
        """
        if self.started: raise RuntimeError( 'must call Stop() method first' )
        if mode: self.Set( ApplicationMode=mode )
        if self.needSetConfig: self.SetConfig()

        if self.mmfilename:
            fullpath = os.path.join( BCI2000LAUNCHDIR, self.mmfilename )
            self.mmfile = open( fullpath, 'r+' )
            self.mmfilesize = os.path.getsize( fullpath ) # TODO: do we need this?
            self.mm = mmap.mmap( self.mmfile.fileno(), self.mmfilesize, access=mmap.ACCESS_WRITE )
            self.mm.seek( 0 )    # simple test of validity
            self.mmlock = threading.Lock()

        self.bci2000( 'set state Running 1' )
        self.started = True

    def ReadMM( self ):
        """
        self.mm is a memory-mapped file (mmap.mmap instance). It serves as the Python end
        of an inter-process communication link for transferring signal data. The other end
        is in the C++ code of the SharedMemoryOutputConnector component of the
        ReflexConditioningSignalProcessing BCI2000 module. self.mm is initialized in Start()
        read/decoded here, and de-initialized in Stop().  ReadMM() is called by GUI.WatchMM(),
        which runs in its own thread (hence the use of self.mmlock, a threading.Lock instance).

        ReadMM() returns a list of lists of floating-point signal values, and a dict of
        floating-point State variable values. Together, these comprise one SampleBlock's worth
        of information from BCI2000.  They are unpacked from shared memory according to
        the protocol established in SharedMemoryOutputConnector::Process(), as follows:
            1. Four unsigned 32-bit integers:
                a. SampleBlock counter
                b. number of channels (will determine the length of the outer list)
                c. number of samples per block (will determine the length of each inner list)
                d. number of State variables (will determine the number of dict entries)
            2. Signal values as a packed array of double-precision floating-point numbers
               in row- (i.e. sample-)first order.
            3. State-variable values as double-precsion floating-point numbers
            4. A space-delimited ASCII byte string specifying the corresponding State variable
               names in order, followed by a newline, followed by a null terminator.
        Since this protocol is for transmission between processes on the *same* CPU, native
        endianness is assumed throughout.
        """
        def chomp( mm, fmt ): return struct.unpack( fmt, mm.read( struct.calcsize( fmt ) ) )
        if not self.started or not self.mm: return None, None
        self.mmlock.acquire()
        self.mm.seek( 0 )
        counter, nChannels, nElements, nStates = chomp( self.mm, '@LLLL' )
        signal = [ [ x / 1e6 for x in chomp( self.mm, '@' + str( nElements ) + 'd' ) ] for channel in range( nChannels ) ]
        statevals = chomp( self.mm, '@' + str( nStates ) + 'd' )
        statestrings = self.mm.readline().strip().split( ' ' )
        states = dict( zip( statestrings, statevals ) )
        self.mmlock.release()
        return signal, states

    def MMCounter( self ):
        """
        Like ReadMM(), but only decode and return the first piece of information in shared memory,
        i.e. the SampleBlock counter.  This is always the last piece of information to be updated
        by SharedMemoryOutputConnector::Process() C++ code on any given SampleBlock, and is
        monitored in the GUI.WatchMM() Python thread to determine when a new SampleBlock is
        available.
        """
        if not self.mm: return 0
        fmt = '@L'
        return struct.unpack( fmt, self.mm[ :struct.calcsize( fmt ) ])[ 0 ]

#### A couple of global functions for dealing with Tkinter widgets


#### Main GUI superclass and subclass

# Definitive translations between mode abbreviations as used in the code, and their formal names as displayed on the GUI tabs / in the title bars of analysis windows / in the log:
MODENAMES = Bunch( st='Stimulus Test', vc='Voluntary Contraction', rc='Recruitment Curve', ct='Control Trials', tt='Training Trials', mixed='Mixed', offline='Offline' )

class GUI( tksuperclass, TkMPL ):
    """
    A class representing the main EPOCS GUI window.  One instance of this, called self, will be created when
    you run EPOCS.  Almost everything else is a child attribute of this GUI instance.  The GUI instance
    will use an Operator instance (stored under self.operator) to manage settings and communicate with BCI2000.
    The GUI instance will be called <self> in an interactive session (i.e. if you run this file from IPython
    and then press ctrl-c to force the GUI update thread into the background).
    """
    def __init__( self, operator=None ):

        tksuperclass.__init__( self )
        TkMPL.__init__( self )

        # Kill any previous instances of Tkinter windows
        try: tkinter.ALLWINDOWS
        except: tkinter.ALLWINDOWS = []
        tkinter.ALLWINDOWS.append( self )
        # NB: if you have a sub-window like an AnalysisWindow open when you restart
        # the GUI, then at this point you may get a message that looks something like
        # invalid command name "189065776callit" while executing "189065776callit" ("after" script)
        # You can ignore it :-)

        self.option_add( '*Font', 'TkDefaultFont 13' )
        self.option_add( '*Label*Font', 'TkDefaultFont 13' )

        self.ready = False
        self.StopFlag = False
        self.iconbitmap( os.path.join( GUIDIR, 'epocs.ico' ) )
        title = 'Evoked Potential Operant Conditioning System'

        try: import win32gui
        except ImportError: pass
        else:
            h = win32gui.FindWindow( 0, title )
            if h != 0:
                tkinter.Label( self, text='Another window called "%s" is already open.\nClose this one, and use the original.' % title ).pack()
                self.update(); time.sleep( 7.0 ); self.destroy(); return
                return

        self.tk_setPalette(
            background=self.colors.button,
            foreground=self.colors.fg,
            #activeBackground='#FFFFFF',
            #activeForeground='#000000',
            selectBackground='#FFFF00',
            selectForeground='#000000',
            disabledBackground=self.colors.button,
            disabledForeground=self.colors.disabled,
        )
        self.title( title )
        self.pendingTasks = {}
        self.pendingFigures = []
        self.pendingFiguresKey = []
        self.afterIDs = {}
        self.messages = Bunch()
        self.states = Bunch( st=Bunch(), vc=Bunch(), rc=Bunch(), ct=Bunch(), tt=Bunch() )
        self.data = Bunch( st=[], vc=[], rc=[], ct=[], tt=[] )
        self.threads = Bunch()
        self.keepgoing = True
        self.mode = None

        ###AMIR - Variables for analyzing the H and M wave based on the parameters in Operator() that define H and M windows
        self.HwaveMag = []
        self.MwaveMag = []
        self.SignalAvg = []
        self.MwaveMagMean = 0
        self.HwaveMagMean = 0
        self.MwaveFigureFlag = 0
        self.channel = 0
        self.nTrials = 0
        ###

        self.controls_location = 'top'
        self.settings_location = 'left'

        if operator == None: operator = Operator()
        self.operator = operator

        self.inifile = os.path.join( GUIDIR, 'epocs.ini' )
        self.operator.Set( **ReadDict( self.inifile ) )

        if DEVEL: self.bind( "<Escape>", self.destroy )

        # Choose the subject ID and whether to start a new or continue an old session:
        if not SubjectChooser( self, initialID=self.operator.params.SubjectName ).successful: self.destroy(); return
        WriteDict( self.operator.params, self.inifile, 'SubjectName', 'DataDirectory' )

        # Launch BCI2000:
        label = tkinter.Label( self, text='Launching BCI2000 system...', font=( 'Helvetica', 15 ) )
        label.grid( row=1, column=1, sticky='nsew', padx=100, pady=100 )
        self.update()
        label.destroy()
        self.protocol( 'WM_DELETE_WINDOW', self.CloseWindow )
        self.operator.Launch()
        self.operator.SetConfig( work_around_bci2000_bug=True )
        self.GetSignalParameters()
        self.SetupDigitimer()

        # Load Modules/Packages
        #LoadPackages(parent=self)
        try:
            self.stimGUI = CurrentControl.CurrentControlWindow(parent=self)
        except:
            pass

        # From here on: configure the GUI
        self.MakeNotebook().pack( expand=1, fill='both', padx=5, pady=5 ,side='top' )

        self.modenames = MODENAMES

        v = self.operator.params._TraceLimitVolts
        self.axiscontrollers_emg1 = []
        self.axiscontrollers_emg2 = []

        matplotlib.pyplot.close( 'all' )

        # OK, you ready?

        # Create the "Stimulus Test" tab
        frame = self.AddTab( 'st', title=self.modenames.st )
        fig, widget, container = self.NewFigure( parent=frame, prefix='st', suffix='emg' )
        self.ControlPanel( 'st', analysis=False )
        self.ProgressPanel( 'st', success=False )
        ax1 = self.artists.st_axes_emg1 = matplotlib.pyplot.subplot( 2, 1, 1 )
        self.artists.st_line_emg1 = matplotlib.pyplot.plot( ( 0, 0 ), ( 0, 0 ), color=self.colors.emg1 )[ 0 ] # NB: axes=blah kwarg doesn't work here
        ax1.grid( True )
        self.axiscontrollers_emg1.append( AxisController(  ax1, 'y', units='V', start=( -v[ 0 ], +v[ 0 ] ), narrowest=( -0.0001, +0.0001 ), widest=( -20.000, +20.000 ) ) )
        self.widgets.st_yadjust_emg1 = PlusMinusTk( parent=frame, controllers=self.axiscontrollers_emg1 ).place( in_=widget, width=20, height=40, relx=0.93, rely=0.25, anchor='w' )
        ax2 = self.artists.st_axes_emg2 = matplotlib.pyplot.subplot( 2, 1, 2 )
        self.artists.st_line_emg2 = matplotlib.pyplot.plot( ( 0, 0 ), ( 0, 0 ), color=self.colors.emg2 )[ 0 ] # NB: axes=blah kwarg doesn't work here
        ax2.grid( True )
        self.axiscontrollers_emg2.append( AxisController(  ax2, 'y', units='V', start=( -v[ 1 ], +v[ 1 ] ), narrowest=( -0.0001, +0.0001 ), widest=( -20.000, +20.000 ) ) )
        self.widgets.st_yadjust_emg2 = PlusMinusTk( parent=frame, controllers=self.axiscontrollers_emg2 ).place( in_=widget, width=20, height=40, relx=0.93, rely=0.75, anchor='w' )
        self.widgets.st_xadjust_emg  = PlusMinusTk( parent=frame, controllers=[ AxisController( ax, 'x', units='s', start=( -0.020,  +0.100  ), narrowest=( -0.002,  +0.010  ), widest=(  -0.100, + 0.500 ) ) for ax in self.MatchArtists( 'st', 'axes' ) ] ).place( in_=widget, width=40, height=20, relx=0.92, rely=0.05, anchor='se' )
        container.pack( side='top', fill='both', expand=True, padx=20, pady=5 )
        frame.pack( side='left', padx=2, pady=2, fill='both', expand=1 )
        chn = ', '.join( self.operator.remote.GetListParameter( 'ChannelNames' ) )
        reminder = 'Configured for %s at %gHz' % ( chn, self.fs )
        if DEVEL: reminder = 'PLAYBACK MODE\n' + reminder
        if len( self.operator.params.TriggerExpression ): reminder += '\nExtra trigger condition: ' + self.operator.params.TriggerExpression
        tkinter.Label( frame.master, text=reminder, bg=self.colors.controls ).place( in_=frame.master, relx=1.0, rely=1.0, anchor='se' )

        # Add the "Voluntary Contraction" tab
        frame = self.AddTab( 'vc', title=self.modenames.vc )
        fig, widget, container = self.NewFigure( parent=frame, prefix='vc', suffix='emg' )
        self.ControlPanel( 'vc' )
        self.ProgressPanel( 'vc', trials=False, success=False )
        self.NewBar( parent=frame, figure=fig, axes=( 1, 2, 1 ), prefix='vc', suffix='background', title='Muscle Activity' )
        container.pack( side='top', fill='both', expand=True, padx=20, pady=5 )
        frame.pack( side='left', padx=2, pady=2, fill='both', expand=1 )


        # Add the "Recruitment Curve" tab
        frame = self.AddTab( 'rc', title=self.modenames.rc )
        fig, widget, container = self.NewFigure( parent=frame, prefix='rc', suffix='emg' )
        self.ControlPanel( 'rc' )
        self.ProgressPanel( 'rc', success=False )
        self.NewBar( parent=frame, figure=fig, axes=( 1, 2, 1 ), prefix='rc', suffix='background', title='Muscle Activity' )
        ax1 = self.artists.rc_axes_emg1 = matplotlib.pyplot.subplot( 2, 2, 2 )
        self.artists.rc_line_emg1 = matplotlib.pyplot.plot( ( 0, 0 ), ( 0, 0 ), color=self.colors.emg1 )[ 0 ]
        ax1.grid( True )
        self.axiscontrollers_emg1.append( AxisController(  ax1, 'y', units='V', start=( -v[ 0 ], +v[ 0 ] ), narrowest=( -0.0001, +0.0001 ), widest=( -20.000, +20.000 ) ) )
        self.widgets.rc_yadjust_emg1 = PlusMinusTk( parent=frame, controllers=self.axiscontrollers_emg1 ).place( in_=widget, width=20, height=40, relx=0.93, rely=0.25, anchor='w' ) # rely=0.75 for subplot( 2, 2, 4 ) only, or rely=0.25 for subplot( 2, 2, 2 ) only / both
        ax2 = self.artists.rc_axes_emg2 = matplotlib.pyplot.subplot( 2, 2, 4 )
        self.artists.rc_line_emg2 = matplotlib.pyplot .plot( ( 0, 0 ), ( 0, 0 ), color=self.colors.emg2 )[ 0 ]
        ax2.grid( True )
        self.axiscontrollers_emg2.append( AxisController(  ax2, 'y', units='V', start=( -v[ 1 ], +v[ 1 ] ), narrowest=( -0.0001, +0.0001 ), widest=( -20.000, +20.000 ) ) )
        self.widgets.rc_yadjust_emg2 = PlusMinusTk( parent=frame, controllers=self.axiscontrollers_emg2 ).place( in_=widget, width=20, height=40, relx=0.93, rely=0.75, anchor='w' ) # rely=0.75 for subplot( 2, 2, 4 ) only, or rely=0.25 for subplot( 2, 2, 2 ) only / both
        self.widgets.rc_xadjust_emg  = PlusMinusTk( parent=frame, controllers=[ AxisController( ax, 'x', units='s', start=( -0.020, +0.100 ), narrowest=( -0.002,  +0.010  ), widest=( -0.100, +0.500 ) ) for ax in self.MatchArtists( 'rc', 'axes' ) ] ).place( in_=widget, width=40, height=20, relx=0.92, rely=0.05, anchor='se' ) # rely=0.52 for subplot( 2, 2, 4 ) only, or rely=0.06 for subplot( 2, 2, 2 ) only / both
        container.pack( side='top', fill='both', expand=True, padx=20, pady=5 )
        frame.pack( side='left', padx=2, pady=2, fill='both', expand=1 )


        # Add the "Control Trials" tab
        frame = self.AddTab( 'ct', title=self.modenames.ct )
        fig, widget, container = self.NewFigure( parent=frame, prefix='ct', suffix='emg' )
        self.ControlPanel( 'ct' )
        self.ProgressPanel('ct', success=False )
        self.NewBar( parent=frame, figure=fig, axes=( 1, 2, 1 ), prefix='ct', suffix='background', title='Muscle Activity' )
        container.pack( side='top', fill='both', expand=True, padx=20, pady=5 )
        frame.pack( side='left', padx=2, pady=2, fill='both', expand=1 )


        # Add the "Training Trials" tab
        frame = self.AddTab( 'tt', title=self.modenames.tt )
        fig, widget, container = self.NewFigure( parent=frame, prefix='tt', suffix='emg' )
        self.ControlPanel( 'tt' )
        self.ProgressPanel( 'tt', success=True )
        self.NewBar( parent=frame, figure=fig, axes=( 1, 2, 1 ), prefix='tt', suffix='background', title='Muscle Activity' )
        self.NewBar( parent=frame, figure=fig, axes=( 1, 2, 2 ), prefix='tt', suffix='response', title='Response' )
        self.artists.tt_line_baseline = matplotlib.pyplot.plot( ( 0, 1 ), ( -1, -1 ), color='#000088', alpha=0.7, linewidth=4, transform=fig.gca().get_yaxis_transform() )[ 0 ]
        container.pack( side='top', fill='both', expand=True, padx=20, pady=5 )
        frame.pack( side='left', padx=2, pady=2, fill='both', expand=1 )

        # Add the "Log" tab
        tab = self.AddTab( 'log', title='Log', makeframe=False )
        logfile = self.operator.LogFile( autoCreate=True )
        frame = self.widgets.log_scrolledtext = ScrolledText( parent=tab, filename=logfile, font='{Courier} 12', bg='#FFFFFF' )
        frame.pack( side='top', padx=2, pady=2, fill='both', expand=1 )

        # Finish up
        self.SetBarLimits( 'vc', 'rc', 'ct', 'tt' )
        self.SetTargets(   'vc', 'rc', 'ct', 'tt' )
        self.DrawFigures()
        #self.resizable( True, False ) # STEP 13 from http://sebsauvage.net/python/gui/
        self.update(); self.geometry( self.geometry().split( '+', 1 )[ 0 ] + '+25+25' ) # prevents Tkinter from resizing the GUI when component parts try to change size (STEP 18 from http://sebsauvage.net/python/gui/ )
        self.wm_state( 'zoomed' ) # maximize the window
        self.ready = True

    def GetSignalParameters( self ):
        """
        Query the few pieces of information that the GUI needs to know back from BCI2000,
        to do its own signal processing. Called after every BCI2000 SETCONFIG command, i.e.
        directly after BCI2000 launch, and also during Start().
        """
        self.fs = float( self.operator.remote.GetParameter( 'SamplingRate' ).lower().strip( 'hz' ) )
        self.sbs = float( self.operator.remote.GetParameter( 'SampleBlockSize' ) )
        self.lookback = float( self.operator.params.LookBack.strip( 'ms' ) ) / 1000.0

    def SetAutomatedParameters(self, mode=None):

        if hasattr(self, 'stimGUI'): self.stimGUI.CurrentAmplitudeState = []
        # AUTOMATED STEPS
        if mode in ['st']:
            self.operator.bci2000('Set Parameter AnalysisType 1') #p2p
            self.operator.needSetConfig = 1
            if hasattr(self, 'stimGUI'):
                self.stimGUI.SetNewCurrent(value=self.stimGUI.CurrentAmplitude / 1000)  # This will in the initial amplitude or update to what the user sets
                self.stimGUI.CurrentAmplitudeState.append(self.stimGUI.CurrentAmplitude)
        if mode in ['rc']:
            self.operator.bci2000('Set Parameter AnalysisType 1')
            self.operator.needSetConfig = 1
            if hasattr(self, 'stimGUI'): self.stimGUI.SetNewCurrent(value=self.stimGUI.CurrentAmplitude / 1000)
        if mode in ['ct','tt']:
            self.operator.bci2000('Set Parameter AnalysisType 0')
            self.operator.needSetConfig = 1
            if hasattr(self, 'stimGUI'): self.stimGUI.SetNewCurrent(value=self.stimGUI.CurrentAmplitude / 1000)

    def Start( self, mode ):
        """
        Start a new run in the specified <mode> (which will be one of 'st', 'vc, 'rc', 'ct' or 'tt').
        One run = one BCI2000 .dat file.
        """
        self.SetAutomatedParameters(mode=mode)
        if hasattr(self,'DS5') and (self.DigitimerEnabled == 'on') and (self.DigitimerSelection == 'DS5'):
            self.DS5.CheckDS5Connected()
            if self.DS5.DS5init:
                self.DS5.AutoZero()
                self.DS5.ToggleOutput(OnOff=True)
            else:
                return

        self.run = 'R%02d' % self.operator.NextRunNumber() # must query this *before* starting the run
        self.operator.Start( mode.upper() )
        self.EnableTab( mode )
        EnableWidget( self.MatchWidgets( mode, 'button' ), False )
        EnableWidget(self.MatchWidgets('mwave', 'button'), False) ###AMIR - Reference text for my widgets contain the mode mwave, this allows me to keep tight control and separate it from the other GUI
        EnableWidget( self.MatchWidgets( mode, 'button', 'stop' ), True )
        self.mode = mode

        UD = getattr(self.operator.params, '_UpDownTrialCount')
        if mode in ['ct','tt'] and UD == 'down':
            N = int(getattr(self.operator.params, '_' + mode + 'TrialsCount'))
            for w in self.MatchWidgets(mode, 'label', 'value', 'trial'): w.config(text=str(N))  # HERE
            self.nTrials = N
        else:
            for w in self.MatchWidgets(mode, 'label', 'value', 'trial'): w.config(text='0')  # HERE

        for w in self.MatchWidgets( mode, 'label', 'value', 'success' ): w.config( text='---', fg='#000000' )
        for w in self.MatchWidgets( mode, 'label', 'title', 'run' ): w.config( text='Now Recording:' )
        for w in self.MatchWidgets( mode, 'label', 'value', 'run' ): w.config( text=self.run )

        self.states[ mode ] = Bunch()
        self.data[ mode ] = []
        self.SignalAvg = []
        self.GetSignalParameters()
        self.block = {}
        self.NewTrial( [ [ 0 ], [ 0 ], [ 0 ], [ 0 ] ], store=False )
        self.SetBarLimits( mode )
        self.SetTargets( mode )
        if hasattr(self, 'mwaveGUI'): self.UpdateMwaveGUI(mode)
        self.UpdateBar( 0.0, True, mode )
        if not self.widgets.log_scrolledtext.filename:
            self.widgets.log_scrolledtext.load( self.operator.LogFile( autoCreate=True ) )
        self.Log( '\n', datestamp=False )
        self.Log( 'Started run %s (%s)' % ( self.run, self.modenames[ self.mode ] ) )
        self.StopFlag = False

    def Stop( self ,mode):
        """
        Stop the current run, if any, closing the associated BCI2000 .dat file.
        """

        if hasattr(self, 'DS5') and (self.DigitimerEnabled == 'on') and (self.DigitimerSelection == 'DS5'):
            self.DS5.ToggleOutput(OnOff=False)

        if (mode in 'st') and hasattr(self,'stimGUI'):
            self.stimGUI.SetNewCurrent(value=0)
            self.stimGUI.currentlabeltxt.set('0.0mA')
            self.stimGUI.CurrentAmplitude = 0

        self.mode = mode
        self.operator.Stop()
        self.EnableTab( 'all' )
        EnableWidget( self.MatchWidgets( self.mode, 'button' ), True )
        EnableWidget( self.MatchWidgets( self.mode, 'button', 'stop' ), False )
        EnableWidget(self.MatchWidgets('mwave', 'button'), True) ###AMIR - Enable M-wave Buttons
        EnableWidget( self.MatchWidgets( self.mode, 'button', 'analysis' ), len( self.data[ self.mode ] ) > 0 )
        for w in self.MatchWidgets( 'label', 'title', 'run' ): w.config( text='Last Recording:' )
        msg = ''
        if self.mode not in [ 'vc' ]: msg = ' after %d trials' % len( self.data[ self.mode ] )
        self.Log( 'Stopped run %s%s' % ( self.run, msg ) )
        self.mode = None
        self.run = None
        self.MwaveMagMean = 0; self.HwaveMagMean = 0; self.MwaveMag = []; self.HwaveMag = []; self.SignalAvg = []


    def UpdateMwaveGUI(self, mode):

        self.HwaveMag = []
        self.MwaveMag = []
        self.SignalAvg = []
        self.MwaveMagMean = 0
        self.HwaveMagMean = 0
        self.MwaveFigureFlag = 0
        self.channel = 0
        self.nTrials = 0

        self.mwaveGUI.mode = mode
        if mode in 'rc': XaxisLimit = 40
        elif mode in 'ct': XaxisLimit = int(getattr(self.operator.params, '_' + 'ct' + 'TrialsCount'))
        elif mode in 'tt': XaxisLimit = int(getattr(self.operator.params, '_' + 'tt' + 'TrialsCount'))
        else: XaxisLimit = 20

        Xticks = range(0, XaxisLimit + 1)
        self.mwaveGUI.axes_seq.set_xlim([0, XaxisLimit + 0.5])
        self.mwaveGUI.axes_seq.set_xticks(Xticks)
        if XaxisLimit == 75: self.self.mwaveGUI.axes_seq.tick_params(axis='x', labelsize=8)
        self.mwaveGUI.axes_seq.grid(True)
        self.mwaveGUI.axes_seq.figure.canvas.draw()

        trialCounterMwave = self.mwaveGUI.widgets.get('mwave_signal_label_value_trial',None)  ###AMIR Added a TrialCounter in the M-Wave Analysis Window
        if mode in ['ct', 'tt']:
            N = getattr(self.operator.params, '_' + mode + 'TrialsCount')
            if trialCounterMwave != None: trialCounterMwave.configure(text='%d' % (N))  ###AMIR Decrease it if it exists
        else:
            if trialCounterMwave != None: trialCounterMwave.configure(text='0')  ###AMIR Decrease it if it exists

        self.MwaveFigureFlag = 1
        self.NewTrial([0], store=False)

        self.MwaveFigureFlag = 2
        self.NewTrial([0,0,0], store=False)

        ###AMIR Don't know a better way but if previous data was opened in M-wave analysis window, I need to re-plot it
        if len(self.MwaveLoadedData):
            self.MwaveFigureFlag = 3
            self.NewTrial([0], store=False)

        self.MwaveFigureFlag = 0

    def SetBarLimits( self, *modes ):
        """
        According to the settings stored in the operator for the upper limits of the
        axes on which the background-EMG and target response bars are displayed,
        as well as the position of the baseline marker (if any), update the graphics
        on the GUI tabs corresponding to the specified *modes.  This is done whenever
        settings might have changed.
        """
        for mode in modes:
            for a in self.MatchArtists( mode, 'axiscontroller', 'background' ):
                a.ChangeAxis( start=( 0, self.operator.GetVolts( self.operator.GetBackgroundBarLimit( mode ) ) ) )
                whichChannel = self.operator.params._FeedbackChannel
                xlabel = 'Muscle Activity'
                if whichChannel.lower() != 'emg1': xlabel += '\n(%s)' % whichChannel
                a.axes.xaxis.label.set( color=self.colors[ whichChannel.lower() ], text=xlabel )
                self.NeedsUpdate( a.axes.figure )

            for a in self.MatchArtists( mode, 'axiscontroller', 'response' ):
                a.ChangeAxis( start=( 0, self.operator.GetVolts( self.operator.params._ResponseBarLimit ) ) )
                whichChannel = self.operator.params._ResponseChannel
                xlabel = 'Response'
                if whichChannel.lower() != 'emg1': xlabel += '\n(%s)' % whichChannel
                a.axes.xaxis.label.set( color=self.colors[ whichChannel.lower() ], text=xlabel )
                self.NeedsUpdate( a.axes.figure )

            for a in self.MatchArtists( mode, 'line', 'baseline' ):
                val = self.operator.GetVolts( self.operator.params._BaselineResponse )
                if val == None: val = -1
                a.set_ydata( ( val, val ) )
                self.NeedsUpdate( a.axes.figure )

    def SetTargets( self, *modes ):
        """
        This updates the positions of the shaded target regions of background-EMG and
        target-response graphs, for the GUI tabs corresponding to the specified *modes.
        This is done whenever settings might have changed.
        """
        for mode in modes:
            if mode in [ 'rc', 'ct', 'tt' ]:
                min, max = self.operator.GetVolts( self.operator.GetBackgroundBarTarget() )
                self.UpdateTarget( min, max, mode, 'target', 'background' )
                min, max = self.operator.GetVolts( self.operator.GetResponseBarTarget()   )
                self.UpdateTarget( min, max, mode, 'target', 'response' )

    def SetTrialCount(self, *modes): ###AS WE HAVE COUNTDOWN COUNTERS NOW...

        UD = getattr(self.operator.params, '_UpDownTrialCount')

        for mode in modes:
            if mode in ['ct', 'tt']:

                trialCounterTitle = self.widgets.get(mode + '_label_title_trial', None)
                trialCounter = self.widgets.get(mode + '_label_value_trial', None)

                if UD == 'down':

                    N = getattr(self.operator.params,'_' + mode + 'TrialsCount')
                    if trialCounter != None: trialCounter.configure(text='%d' % (N))
                    trialCounterTitle.configure(text='Trials Remaining')
                    if hasattr(self,'mwaveGUI') and (self.mwaveGUI.mode in mode):
                        trialCounterMwave = self.mwaveGUI.widgets.get('mwave_signal_label_value_trial', None)  ###AMIR Added a TrialCounter in the M-Wave Analysis Window
                        trialCounterMwaveTitle = self.mwaveGUI.widgets.get('mwave_signal_label_title_trial', None)
                        if trialCounterMwave != None:
                            trialCounterMwave.configure(text='%d' % (N))  ###AMIR Decrease it if it exists
                            trialCounterMwaveTitle.configure(text='Trials Remaining')
                else:
                    trialCounterTitle.configure(text='Trials Completed')
                    trialCounter.configure(text='0')
                    if hasattr(self,'mwaveGUI') and (self.mwaveGUI.mode in mode):
                        trialCounterMwave = self.mwaveGUI.widgets.get('mwave_signal_label_value_trial', None)  ###AMIR Added a TrialCounter in the M-Wave Analysis Window
                        trialCounterMwaveTitle = self.mwaveGUI.widgets.get('mwave_signal_label_title_trial', None)
                        if trialCounterMwave != None:
                            trialCounterMwave.configure(text='0')  ###AMIR Decrease it if it exists
                            trialCounterMwaveTitle.configure(text='Trials Completed')

    def SetIncrement(self):

        #For some reason my StringVar() associated with the SpinBox in the Current Control Window changes but the text will not change...
        #Workaround, I destroy the stimbox and re-initiate it
        if hasattr(self, 'stimGUI'):
            self.stimGUI.incrementtxt.set(str(self.operator.params._IncrementStart))
            self.stimGUI.incrementlabel['increment'] = str(self.operator.params._IncrementIncrement)
            self.stimGUI.CurrentLimit = self.operator.params._CurrentLimit

    def SetupDigitimer(self):
        import tkMessageBox
        #DS5 = bool(self.operator.remote.GetParameter('EnableDS5ControlFilter'))
        #DS8 = bool(self.operator.remote.GetParameter('EnableDS8ControlFilter'))

        self.DigitimerEnabled = self.operator.params._DigitimerEnable
        self.DigitimerSelection = self.operator.params._DigitimerSelect

        if self.DigitimerEnabled == 'on':
            # Also check if the user has run NIAnalogOutput
            DigitimerSetup = os.path.isfile('../parms/NIDigitalOutputPort.prm')
            #TODO: Check that the parameter file first line actually contains a valid digital and anlog setting.
            if not DigitimerSetup:
                tkMessageBox.showinfo('DS5/DS8', 'You have not run app\NIDevicesAO.bat. If using DS5 please also run NIDevicesAO.')
            if self.DigitimerSelection == 'DS5':
                self.operator.bci2000('set parameter EnableDS5ControlFilter 1')
                self.operator.bci2000('set parameter AnalogOutput 1')
                self.operator.bci2000('set parameter EnableDS8ControlFilter 0')
                self.DS5 = DS5LibClass(DS5_BCI2000_parameter=True)
            if self.DigitimerSelection == 'DS8':
                self.operator.bci2000('set parameter EnableDS8ControlFilter 1')
                self.operator.bci2000('set parameter EnableDS5ControlFilter 0')
                self.operator.bci2000('set parameter AnalogOutput 0')
        else:
            self.operator.bci2000('set parameter EnableDS5ControlFilter 0')
            self.operator.bci2000('set parameter AnalogOutput 0')
            self.operator.bci2000('set parameter EnableDS8ControlFilter 0')

    def SettingsFrame( self, code, settings=True, analysis=True ):
        """
        Create and lay out the "Analysis" and "Settings" buttons.  Called once for each
        GUI tab, with <code> equal to 'st', 'vc', 'rc', 'ct' or 'tt' in each case, during
        construction.
        """
        if settings: settings_tag = '_button_settings'
        else: settings_tag = '_fakebutton_settings'
        if analysis: analysis_tag = '_button_analysis'
        else: analysis_tag = '_fakebutton_analysis'
        parent = self.widgets[ code + '_frame_controls' ]
        frame = self.widgets[ code + '_frame_settings' ] = tkinter.Frame( parent, bg=parent[ 'bg' ] )
        if code in ['st'] and hasattr(self,'stimGUI'):
            button = self.widgets[ code + analysis_tag ] = tkinter.Button( frame, text='Analysis', command = Curry( STAnalysisWindow, parent=self, mode=code ) )
        else:
            button = self.widgets[ code + analysis_tag ] = tkinter.Button( frame, text='Analysis', command = Curry( AnalysisWindow, parent=self, mode=code, geometry='parent' ) )

        EnableWidget( button, False )
        button.pack( side='top', ipadx=20, padx=2, pady=2, fill='both' )
        button = self.widgets[ code + settings_tag ]    = tkinter.Button( frame, text='Settings',    command = Curry( SettingsWindow, parent=self, mode=code ) )
        EnableWidget( button, settings )
        button.pack( side='bottom', ipadx=20, padx=2, pady=2, fill='both' )
        frame.pack( side=self.settings_location, fill='y', padx=5 )


    def LoadDemoData( self, code ):
        import pickle
        self.data[ code ] = pickle.load( open( 'ExampleData.pk', 'rb' ) )[ code ]
        EnableWidget( self.MatchWidgets( code, 'button', 'analysis' ), len( self.data[ code ] ) > 0 )

    def MWaveAnalysisFunc(self, code):
        ###AMIR Function that calls the M-wave analyis GUI

        if not hasattr(self,'mwaveGUI'): self.mwaveGUI = MWaveAnalysisWindow(parent=self,mode=code,operator=self.operator)

    def ControlPanel( self, code, **kwargs ):
        """
        Create and lay out, on the GUI tab indicated by the two-letter <code>, a frame
        containing all the necessary buttons (Start, Stop, Analysis, Settings) as well
        as information panels (subject and session ID, last run).
        """
        tabkey = code + '_tab'
        tab = self.widgets[ code + '_tab' ]
        frame = self.widgets[ code + '_frame_controls' ] = tkinter.Frame( tab, bg=self.colors.controls )
        button = self.widgets[ code + '_button_start' ] = tkinter.Button( frame, text='Start', command = Curry( self.Start, mode=code ) )
        button.pack( side='left', ipadx=20, ipady=20, padx=2, pady=2, fill='y' )
        button = self.widgets[ code + '_button_stop'  ] = tkinter.Button( frame, text='Stop',  command = Curry(self.Stop, mode=code), state='disabled' )
        button.pack( side='left', ipadx=20, ipady=20, padx=2, pady=2, fill='y' )

        self.SettingsFrame(code, **kwargs)

        if hasattr(self,'stimGUI'):
            Cbutton = self.widgets[code + 'stim'] = tkinter.Button(frame, text='Stimulation\nControl Panel', command=self.stimGUI.deiconify)
            Cbutton.pack(side='left', ipadx=20, padx=2, pady=2)

            DS5 = int(self.operator.remote.GetParameter('EnableDS5ControlFilter'))
            DS8 = int(self.operator.remote.GetParameter('EnableDS8ControlFilter'))
            if (DS5 == 0) and (DS8 == 0):
                Cbutton.config(state='disabled')

        if DEVEL and code in [ 'vc', 'rc', 'ct', 'tt' ]:
            button = self.widgets[ code + '_button_load' ] = tkinter.Button( frame, text='Load\nDemo Data', command=Curry( self.LoadDemoData, code=code ) )
            button.pack( side='left', ipadx=20, padx=2, pady=2 )
        if code in ['ct','tt']: ###AMIR Button in the CT, RC OR TT to generate the M-Wave window (class)
            Mbutton = self.widgets[ code + '_button_mwave' ] = tkinter.Button( frame, text='M-Wave\nAnalysis', command= Curry(self.MWaveAnalysisFunc,code=code))
            Mbutton.pack(side='left', ipadx=20, padx=2, pady=2)

        self.InfoFrame( code, 'subject', 'Patient ID:', self.operator.params.SubjectName ).pack( side='left', fill='y', padx=5, pady=2, expand=1 )
        self.InfoFrame( code, 'session', 'Session Started At:', self.operator.FriendlyDate() ).pack( side='left', fill='y', padx=5, pady=2, expand=1 )
        lastRun = self.operator.LastRunNumber( mode=code )
        if lastRun: lastRun = 'R%02d' % lastRun
        else: lastRun = '---'
        self.InfoFrame( code, 'run', 'Last Recording:', lastRun ).pack( side='left', fill='y', padx=5, pady=2, expand=1 )
        frame.pack( side=self.controls_location, fill='x', padx=2, pady=2 )
        #frame.grid( row=2, column=1, columnspan=2, sticky='nsew' )
        return frame

    def NewBar( self, parent, prefix, suffix, figure=None, axes=None, **kwargs ):
        """
        Create a new figure on the Tkinter.Frame <parent>, unless a <figure> is already
        supplied.  Create a new axes artist on that figure, unless an <axes> instance
        is already supplied.  Create an associated AxisController for the vertical axis
        and draw a patch that will form the feedback bar.  Store all the relevant widgets
        and artists in self.widgets and self.artists, using the specified <prefix> and
        <suffix> in the manner of NewFigure()  (see the TkMPL superclass documentation).
        """
        widget = None
        if figure == None and isinstance( axes, ( tuple, list, type( None ) ) ):
            figure, widget, container = self.NewFigure( parent=parent, prefix=prefix, suffix=suffix )
        if isinstance( axes, ( tuple, list ) ):
            axes = self.artists[ prefix + '_axes_' + suffix ] = matplotlib.pyplot.subplot( *axes )
        if axes == None: axes = self.artists[ prefix + '_axes_' + suffix ] = matplotlib.pyplot.axes()
        if figure == None: figure = axes.figure
        if widget == None: widget = figure.canvas.get_tk_widget()
        aspect = kwargs.pop( 'aspect', 3 )
        barwidth = kwargs.pop( 'width', 0.5 )
        ylim = kwargs.pop( 'ylim', ( 0, 0.02 ) )
        grid = kwargs.pop( 'grid', True )
        xlabel = kwargs.pop( 'xlabel', '' )
        title = kwargs.pop( 'title', '' )
        targetMin, targetMax = kwargs.pop( 'target', ( 0, 0 ) )
        edgecolor = kwargs.pop( 'edgecolor', 'none' )
        facecolor = kwargs.pop( 'facecolor', self.colors.good )
        if self.controls_location == 'top': xlabel, title = title, xlabel
        axes.set( ylim=ylim, xlim=( 0, 1 ), xlabel=xlabel, xticks=(), title=title )
        axes.xaxis.label.set_size( axes.title.get_size() )
        #axes.set_adjustable( 'box' ); axes.set_aspect( aspect ) # doesn't seem to work: change the y-axis data limits, and the physical axes shape still changes
        axes.yaxis.grid( grid )
        pos = axes.get_position()
        pos = list( pos.min ) + list( pos.size )
        width = pos[ 3 ] / aspect
        pos[ 0 ] += ( pos[ 2 ] - width ) / 2.0
        pos[ 2 ] = width
        axes.set_position( pos )
        self.artists[ prefix + '_axiscontroller_' + suffix ] = AxisController( axes, 'y', units='V', start=ylim )
        hatch = 'x'
        if matplotlib.__version__ >= '1.3': hatch = 'xx'
        target = self.artists[ prefix + '_target_' + suffix ] = matplotlib.patches.Rectangle( xy=( 0, targetMin ), width=1, height=targetMax - targetMin, hatch=hatch, facecolor='#FFFFFF', edgecolor='#000000', transform=axes.get_yaxis_transform() )
        # NB: a bug in matplotlib seems to cause a rectangle with hatch='x', facecolor='none', edgecolor='none' to appear only partially
        # filled under some circumstances e.g. when its bounds exceed those of the axes it's on).  Setting facecolor='#FFFFFF' is a workaround for this)
        axes.add_patch( target )
        bar = self.artists[ prefix + '_bar_' + suffix ] = matplotlib.patches.Rectangle( xy=( 0.5 - 0.5 * barwidth, 0 ), width=barwidth, height=max( ylim ) * 0.0, transform=axes.get_yaxis_transform(), edgecolor=edgecolor, facecolor=facecolor, alpha=0.9, **kwargs )
        axes.add_patch( bar )
        text = self.artists[ prefix + '_text_' + suffix ] = axes.text( 0.5, 0.98, '', transform=axes.transAxes, horizontalalignment='center', verticalalignment='top' )
        return figure, widget, widget.master, axes, bar

    def NeedsUpdate( self, fig ):
        """
        Flag the specified matplotlib.pyplot.figure instance <fig> as needing to be re-drawn.
        """
        if (fig not in self.pendingFigures) or (hasattr(self,'mwaveGUI')): ###AMIR Had to edit this as we have 2 lines in each figure of the M-wave analysis window, so update fig called twice
            self.pendingFigures.append( fig )

    def UpdateTarget( self, min, max, *terms ):
        """
        Lower-level routine, called by SetTargets(), for changing the position of one or
        more shaded target regions.
        """
        for target in self.MatchArtists( 'target', *terms ):
            if min == None: min = 0.0
            if max == None: max = target.axes.get_ylim()[ 1 ]
            target.set( y=min, height=max - min )
            self.NeedsUpdate( target.figure )

    def UpdateBar( self, height, good, *terms ):
        """
        Change the height and color of one or more feedback bars.
        """
        keys, things = self.Match( self.artists, 'bar', *terms )
        if len( keys ) == 0: return
        key = keys[ 0 ]
        bar = self.artists[ key ]
        if good == None:
            target = self.artists[ key.replace( '_bar_', '_target_' ) ]
            targetMin = target.get_y()
            targetMax = targetMin + target.get_height()
            if targetMax > 0 and not targetMin <= height <= targetMax: good=False
            else: good=True
        if good: color=self.colors.good
        else: color=self.colors.bad
        bar.set( height=height, color=color )
        text = self.artists[ key.replace( '_bar_', '_text_' ) ]
        ylim = bar.axes.get_ylim()
        if height > max( ylim ):
            controller = self.artists[ key.replace( '_bar_', '_axiscontroller_' ) ]
            val = FormatWithUnits( value=height, context=ylim, units=controller.units, appendUnits=True )
            text.set_text( val )
        elif text.get_text() != '': text.set_text( '' )
        self.NeedsUpdate( bar.figure )

    def After( self, msec, key, func ):
        """
        Wraps the Tkinter.Tk.after() method - i.e. the method for calling <func>
        after a delay of <msec> milliseconds safely in a Tk-compatible background thread.
        The <key> is used to identify the operation: any pending calls with the same key
        are cancelled before registering this one.
        """
        old = self.afterIDs.get( key, None )
        if old != None: self.after_cancel( old )
        self.afterIDs[ key ] = self.after( msec, func )

    def GetDescription( self, mode ):
        """
        Called by the AnalysisWindow constructor to know how to refer to the current
        data. For the online GUI, we'll just use the label of the current run (e.g. 'R06').
        """
        return self.MatchWidgets( mode, 'label', 'value', 'run' )[ 0 ][ 'text' ]

    def CloseWindow( self ):
        """
        Callback called when the user attempts to close the main window. If a run is
        still running, the attempt is denied.  If not, an "are you sure?" confirmation
        dialog is implemented.
        """
        if self.mode != None: return
        if getattr( self, 'areyousure', False ): return
        w, h, propx, propy = 400, 150, 0.5, 0.5
        pw, ph, px, py = [ float( x ) for x in self.geometry().replace( '+', 'x' ).split( 'x' ) ]
        #pw, ph, px, py = self.winfo_screenwidth(), self.winfo_screenheight(), 0, 0
        geometry = geometry='%dx%d+%d+%d' % ( w, h, ( pw - w ) * propx + px, ( ph - h ) * propy + py )
        self.areyousure = True
        sure = Dialog( self, geometry=geometry, message='Are you sure you want to\nquit EPOCS?' ).result
        self.areyousure = False
        if sure: self.destroy()

    def destroy( self, arg=None ):
        """
        Overshadows and wraps the standard destroy() method of the Tk superclass.
        Stops ongoing threads, cancels pending tasks, saves settings, shuts down BCI2000
        and closes matplotlib figures before finally destroying the widget.
        """
        self.StopThreads()
        if getattr( self, 'operator', None ):
            con1 = getattr( self, 'axiscontrollers_emg1', [ None ] )[ 0 ]
            if con1: self.operator.params._TraceLimitVolts[ 0 ] = max( con1.get() )
            con2 = getattr( self, 'axiscontrollers_emg2', [ None ] )[ 0 ]
            if con2: self.operator.params._TraceLimitVolts[ 1 ] = max( con2.get() )
            if self.operator.sessionStamp:
                try: self.operator.WriteSubjectSettings()
                except: pass
            if self.operator.remote: self.operator.bci2000( 'quit' )

        if getattr( self, 'afterIDs', None ):
            for k in self.afterIDs.keys():
                self.after_cancel( self.afterIDs.pop( k ) )
        try: tksuperclass.destroy( self )
        except: pass
        for x in self.MatchArtists( 'figure' ): matplotlib.pyplot.close( x )
        time.sleep( 0.25 )
        self.quit()

    def Log( self, text, datestamp=True ):
        """
        Callback for logging results information.
        """
        if datestamp: stamp = self.operator.FriendlyDate( time.time() ) + '       '
        else: stamp = ''
        self.widgets.log_scrolledtext.append( stamp + text + '\n', ensure_newline_first=True )

    def ScheduleTask( self, key, func ):
        """
        Add a callable <func> to the set of tasks that should be performed during
        the regular calls to HandlePendingTasks().
        """
        self.pendingTasks[ key ] = func

    def HandlePendingTasks( self ):
        """
        Call, and remove from the pending list, any tasks registered with ScheduleTask().
        Note that functions are not called in any defined order.
        Also, re-draw any figures that have been flagged with NeedsUpdate().
        Finally, re-schedule the next call of HandlePendingTasks after a fixed short
        interval, using After().  The initial registration happens in Loop(), which is
        called in the __main__ part of the file.
        """
        for v in self.pendingTasks.values(): v()
        self.pendingTasks.clear()

        ###AMIR changed this, as I am plotting on top of the Mwave figure so need to have it in the list twice
        ### 	working on the assumption that the 2nd addition to pendingFigures of the same line will be right after the first call

        while len( self.pendingFigures ):

            #while fig in self.pendingFigures: self.pendingFigures.remove( fig )
            fig = self.pendingFigures.pop( 0 )

            if self.pendingFiguresKey:	key = self.pendingFiguresKey.pop( 0 ) ###This just let's me know if it is a normal plot, signal average or the sequence
            else: key = 'base'

            if key == 'base':
                fig.canvas.draw() ###AMIR Repeat flag tells me the same figure is called twice (which is the case for plotting Signal Average and the Signal)
            elif key == 'SignalAvg':
                fig.hold(True)
                fig.canvas.draw()
                fig.hold(False)
            elif key == 'Sequence':
                fig.hold(True)
                fig.canvas.draw()
            else: fig.canvas.draw()

        self.After( 10, 'HandlePendingTasks', self.HandlePendingTasks )

        if self.StopFlag:
            self.Stop(mode=self.mode)
            self.StopFlag = False

    def WatchMM( self ):
        """
        Check at 1-millisecond intervals until the Operator's shared memory area reports
        that a new SampleBlock has been made available by BCI2000. When a new block arrives,
        read it, decode it, and schedule it for processing.

        NB: this is run in a thread, and TkInter is not thread-safe. So we cannot touch
        any Tk widgets from this code. We use ScheduleTask instead - HandlePendingTasks
        mops these up every 10ms.
        """
        counter = prev = 0
        while self.keepgoing:
            while self.keepgoing and ( counter == prev or counter == 0 ):
                time.sleep( 0.001 )
                counter = self.operator.MMCounter()
            if self.keepgoing:
                prev = counter
                signal, states = self.operator.ReadMM()
                self.ScheduleTask( 'update_states_and_signal', Curry( self.ProcessStatesAndSignal, states=states, signal=signal ) )

    def ProcessStatesAndSignal( self, states, signal ):
        """
        Called with the decoded contents of shared memory whenever a new SampleBlock arrives
        from BCI2000. First calls Incoming() to deal with the incoming state variables.
        Then, if the result of this indicates that a new *trial* has arrived (i.e. the
        TrialsCompleted state variable has increased).
        """
        if self.Incoming( states, 'States' ):
            self.Incoming( signal, 'Signal' )

    def Incoming( self, block, queue ):
        """
        Process information in <block> in the context specified by <queue>.  <queue>
        may be 'Signal' or 'States'.

        In the 'States' queue, this method returns True if a change in the state variable
        TrialsCompleted indicates that a new trial has arrived, or False otherwise.
        This code also updates the visible trial counter and success-rate counter.

        The 'Signal' queue assumes that the signal belongs to a new trial and passes
        it straight on to NewTrial().

        Sorry about this slightly convoluted way of doing things: the architecture was
        designed during the transition/performance-debugging period between UDP
        ConnectorOutput communication and shared-memory communication.  There used to be
        an alternative queue called 'ConnectorOutput' for the UDP information.
        """
        code = self.mode
        if code == None: return False
        states = self.states[ code ]

        if block == None: return False
        UD = getattr(self.operator.params, '_UpDownTrialCount', None)
        if UD == None: UD = 'up'

        if queue == 'Signal':
            #As signal follows state then we can assume a change (i.e. TrialsCompleted Changed)...
            self.NewTrial( block )

            if hasattr(self,'mwaveGUI'): ###AMIR only run this if the GUI exists
                self.AnalyzeValues( block, states ) ###AMIR New function to extract H and W Signal Features


                ###AMIR Update M-wave Panel mean and current value: TODO, MOVE ALL THESE INTO THEIR OWN SET OF FUNCTIONS
                self.panel.MeanM.set(self.MwaveMagMean)
                self.panel.LastM.set(self.MwaveMag[int(len(self.MwaveMag)-1)])

                #AMIR Plot the Average on top of the current relevant axes
                self.MwaveFigureFlag = 1
                self.NewTrial(self.SignalAvg,store=False)

                #Sequence Plot on Mwave Analysis Window
                self.MwaveFigureFlag = 2
                self.NewTrial([range(1,int(states.TrialsCompleted)+1), self.MwaveMag, self.HwaveMag], store=False)
                if int(self.mwaveGUI.axes_seq.get_xlim()[1]-0.5) < int(states.TrialsCompleted):
                    self.mwaveGUI.axes_seq.set_xlim([0, int(states.TrialsCompleted) + 0.5])
                    Xticks = range(0, int(states.TrialsCompleted) + 1)
                    self.mwaveGUI.axes_seq.set_xticks(Xticks)
                    self.mwaveGUI.artists.axes_emg_seq_mwave.grid(True)

                ###AMIR Don't know a better way but if previous data was opened in M-wave analysis window, I need to re-plot it
                if len(self.MwaveLoadedData):
                    self.MwaveFigureFlag = 3
                    self.NewTrial(self.MwaveLoadedData, store=False)

                self.MwaveFigureFlag = 0

            if code in ['ct','tt'] and UD=='down':
                if (int(self.nTrials) == 0):
                    self.StopFlag = True

            return False

        if len( states ) == 0:
            states.update( block )
            return False

        newTrial = False
        changed = Bunch( ( k, False ) for k in states )
        for key, value in block.items():
            changed[ key ] = ( states.get( key, None ) != value )
            states[ key ] = value

        if self.mode in [ 'vc' ]: self.data[ self.mode ].append( states.BackgroundFeedbackValue / 1000000.0 )

        if changed.BackgroundFeedbackValue or changed.BackgroundGreen:
            height = states.BackgroundFeedbackValue / 1000000.0
            good = ( states.BackgroundGreen != 0.0 )
            self.UpdateBar( height, good, code, 'background' )

        if changed.ResponseFeedbackValue or changed.ResponseGreen:
            height = states.ResponseFeedbackValue / 1000000.0
            good = ( states.ResponseGreen != 0.0 )
            self.UpdateBar( height, good, code, 'response' )

        #if changed.EnableTrigger:
        #	self.stimGUI.GetCurrent(mode=code)

            #Set the new current the user sees when EnableTrigger is set. We then know what the person was just stimulated with

        if changed.TrialsCompleted: # the TrapFilter.cpp filter inside the ReflexConditioningSignalProcessing.exe module increments the TrialsCompleted state variable to indicate that a new trial has been trapped

            trialCounter = self.widgets.get( code + '_label_value_trial', None )
            successCounter = self.widgets.get( code + '_label_value_success', None )

            if hasattr(self,'mwaveGUI'): trialCounterMwave = self.mwaveGUI.widgets.get('mwave_signal_label_value_trial', None) ###AMIR Added a TrialCounter in the M-Wave Analysis Window
            else: trialCounterMwave = None

            #For this version to plot the RC currents I need to add the current to the states
            #DS5 = int(self.operator.remote.GetParameter('EnableDS5ControlFilter'))
            #if DS5 == 1:
            if hasattr(self, 'stimGUI'): self.stimGUI.CurrentAmplitudeState.append(self.states[code].CurrentAmplitude)

            if self.mode in ['ct','tt'] and UD=='down':
                # LOAD UP THE SETTING
                N = getattr(self.operator.params, '_' + code + 'TrialsCount')
                self.nTrials = int(N - states.TrialsCompleted)
                if trialCounter != None: trialCounter.configure(text='%d' % (self.nTrials))
                if trialCounterMwave != None: trialCounterMwave.configure(
                    text='%d' % (self.nTrials))  ###AMIR Decrease it if it exists
            else:
                if trialCounter != None:
                    trialCounter.configure( text='%d' % states.TrialsCompleted )
                if trialCounterMwave != None:
                    trialCounterMwave.configure(text='%d' % states.TrialsCompleted) ###AMIR Increment it if it exists


            if states.TrialsCompleted == 0:
                states.SuccessfulTrials = None
                if successCounter != None: successCounter.configure( text='---', fg='#000000' )
            else:
                newTrial = True
                if successCounter != None:
                    percent = 100.0 * float( states.SuccessfulTrials ) / float( states.TrialsCompleted )
                    percent = '%.1f' % percent
                    if float( percent ) == 100: percent = '100'
                    #if percent <= 50.0: color = self.colors.bad
                    #else: color = self.colors.good
                    color = '#000000'
                    successCounter.configure( text='%s%%' % percent, fg=color )
                if queue == 'ConnectorOutput':  # in BCI2000's traditional ConnectorOutput protocol, the signal is present on every block, mixed in with the states
                    self.NewTrial( block )

        return newTrial

    def	NewTrial( self, signal, store=True ,**kwargs ):
        """
        Called during Incoming() operations on the 'Signal' queue, which is called during
        ProcessStatesAndSignal() if there is an increment in the TrialsCompleted state
        variable indicating that a new trial has arrived (ProcessStatesAndSignal itself is
        called indirectly via ScheduleTask() during the WatchMM() thread).

        Stores the data, and updates any graphical traces of the EMG epoch.
        """
        if signal == None: return
        if store and self.mode not in [ 'vc' ]:	self.data[ self.mode ].append( signal )

        if self.MwaveFigureFlag == 0: ###AMIR First part same as previous version
            for channelIndex, values in enumerate( signal ):
                lines = self.MatchArtists( self.mode, 'line', 'emg' + str( channelIndex + 1 ) )
                if len( lines ) == 0: continue
                for line in lines:
                    line.set( xdata=TimeBase( values, self.fs, self.lookback ), ydata=values )
                    self.NeedsUpdate( line.figure )
                    self.pendingFiguresKey.append('base')
        ###AMIR However, if the M-wave Analysis Window Exists then we want to process the SignalAvg which has no channel indices
        elif self.MwaveFigureFlag == 1:
                lines = self.MatchArtists(self.mode, 'line', 'sigavg','mwave')
                for line in lines:
                    line.set(xdata=TimeBase(signal, self.fs, self.lookback), ydata=signal)
                    self.NeedsUpdate(line.figure)
                    self.pendingFiguresKey.append('SignalAvg')
        elif self.MwaveFigureFlag == 2:  ###AMIR We are updating the M wave sequence plot which is one value at a time...
                    lines = self.MatchArtists('sequenceM','line', 'mwave')
                    for line in lines:
                        line.set(xdata=signal[0], ydata=signal[1])
                        self.NeedsUpdate(line.figure)
                        self.pendingFiguresKey.append('Sequence')
                    lines = self.MatchArtists('sequenceH', 'line', 'mwave')
                    for line in lines:
                        line.set(xdata=signal[0], ydata=signal[2])
                        self.NeedsUpdate(line.figure)
                        self.pendingFiguresKey.append('Sequence')
        else:
            lines = self.MatchArtists('loaded','prevdata','mwave')
            for line in lines:
                line.set(xdata=signal[0], ydata=signal[1])
                self.NeedsUpdate(line.figure)
                self.pendingFiguresKey.append('sigavg')

    def AnalyzeValues(self, signal, states):
        """
        ###AMIR A new function to analyze H and M values
        Called during Incoming() to analyze some of the signal parameters to be passed onto the Mwave GUI.
        This includes extracting the H and M wave response based on previously saved indices in the operator parameters.
        The mean of the M and H waves and the signal average are also computed.
        """

        self.HwaveMag.append(states.ResponseFeedbackValue/1e6)
        self.MwaveMag.append(states.ReferenceFeedbackValue/1e6)

        self.MwaveMagMean = sum(self.MwaveMag) / len(self.MwaveMag)
        self.HwaveMagMean = sum(self.HwaveMag) / len(self.HwaveMag)

        x = self.SignalAvg
        y = signal[self.channel]

        if  len(self.SignalAvg):
            temp = [(a+b)/2 for a,b in zip(x,y)]
            self.SignalAvg = temp
            #for xindex, value in enumerate(signal[self.channel]): self.SignalAvg[xindex] = (self.SignalAvg[xindex] + value) / 2 #THIS STATEMENT FOR SOME REASON ASSIGNS THE FIRST TRIAL AS THE AVERAGE...
        else: self.SignalAvg = signal[self.channel]



    def StartThread( self, name, func, *pargs, **kwargs ):
        """
        Create, register and start a threading.Thread which runs the specified <func>
        with the specified positional arguments and keyword arguments.

        NB: TkInter is not thread-safe, so the code in <func> should not touch any Tk widgets.
        ScheduleTask can be used instead - HandlePendingTasks mops these up every 10ms.
        """
        t = self.threads[ name ] = threading.Thread( target=func, args=pargs, kwargs=kwargs )
        t.start()

    def StopThreads( self ):
        """
        Set the self.keepgoing flag to False.  Thread target functions should monitor this
        flag.
        """
        self.keepgoing = False

    def Loop( self ):
        """
        This is the "main" function of the GUI.  It is called during the __main__ part of
        the Python file (i.e. when the file is run). It can be interrupted with ctrl-c:
        the shared-memory thread then halts, but everything else (e.g. tk updates) continues
        to happen in the background.
        """
        self.keepgoing = True
        self.StartThread( 'watch_mm', self.WatchMM )
        self.After( 50, 'HandlePendingTasks', self.HandlePendingTasks )
        try: self.mainloop()
        except KeyboardInterrupt: pass
        self.StopThreads()


class Dialog( tkinter.Toplevel ):
    """ Modal dialog box adapted from that of Fredrik Lundh: http://effbot.org/tkinterbook/tkinter-dialog-windows.htm """
    def __init__( self, parent, title=None, icon=None, geometry=None, blocking=True, modal=True, message='Hello World!', buttons=( 'OK', 'Cancel' ) ):
        """
        Set modal=False to instantiate this as a normal window (with buttons to maximize,
        minimize or close it).

        With modal=True and blocking=True, this constructor will not return until the
        dialog is dismissed.
        """
        tkinter.Toplevel.__init__( self, parent )
        if parent and modal: self.transient( parent )
        if title: self.title( title )
        if icon: self.iconbitmap( icon )
        if geometry == None and hasattr( parent, 'winfo_rootx' ):
            geometry = "+%d+%d" % ( parent.winfo_rootx() + 10, parent.winfo_rooty() + 30 )
        self.desired_geometry = geometry
        self.parent = parent
        self.result = None
        self.buttons = buttons # used in default buttonbox() implementation, but not necessarily if that is overshadowed
        self.message = message # used in default body() implementation, but not necessarily if that is overshadowed
        body = tkinter.Frame( self )
        self.initial_focus = self.body( body )
        body.pack( side='top', fill='both', expand=True, padx=5, pady=5 )
        self[ 'bg' ] = body[ 'bg' ]
        self.buttonbox()
        if geometry != None: self.geometry( geometry )
        if modal: self.grab_set()
        if not self.initial_focus: self.initial_focus = self
        self.protocol( "WM_DELETE_WINDOW", self.cancel )
        self.initial_focus.focus_set()
        if modal and blocking: self.wait_window( self )

    # construction hooks

    def body( self, master ):
        tkinter.Label( master, text=self.message ).pack( fill='both', expand=1, padx=10, pady=5 )
        # create dialog body. return widget that should have initial focus. this method should be overridden

    def buttonbox( self ):
        # add standard button box. override if you don't want the
        # standard buttons
        if not self.buttons: return
        self.footer = tkinter.Frame( self, bg=self[ 'bg' ] )
        default = tkinter.ACTIVE
        for button in self.buttons:
            command = { 'ok' : self.ok, 'cancel' : self.cancel }.get( button.lower(), None )
            w = tkinter.Button( self.footer, text=button, width=10, command=command, default=default )
            w.pack( side=tkinter.LEFT, padx=5, pady=5 )
            if command == self.ok: self.bind( "<Return>", command )
            if command == self.cancel: self.bind( "<Escape>", command )
            default = None
        self.footer.pack( side='bottom' )

    # standard button semantics
    def ok(self, event=None):
        if not self.validate(): self.initial_focus.focus_set(); return  # put focus back
        self.withdraw()
        self.update_idletasks()
        self.apply()
        self.cancel()
    def cancel(self, event=None):
        # put focus back to the parent window
        if self.parent and hasattr( self.parent, 'focus_set' ): self.parent.focus_set()
        self.destroy()

    # command hooks
    def validate(self): return True # override
    def apply(self): self.result = True # override

class ScrolledText( tkinter.Frame ):
    """
    A text area into which the user can type arbitrary text. Supports ctrl-x/c/v for
    cut/copy/paste, and ctrl-z/y for undo/redo.  Optionally can save the text
    automatically to a specified file.

    Adapted from Stephen Chappell's post at http://code.activestate.com/recipes/578569-text-editor-in-python-33/
    """
    def __init__( self, parent=None, text='', filename=None, **kwargs ):
        tkinter.Frame.__init__( self, parent )
        self.scrollbar = tkinter.Scrollbar( self )
        self.text = tkinter.Text( self, relief='sunken', wrap='word', undo=True, **kwargs )
        self.text.bind( "<Control-z>", self.undo )
        self.text.bind( "<Control-y>", self.redo )
        self.text.bind( "<KeyRelease>", self.active )
        self.scrollbar[ 'command' ] = self.text.yview
        self.text[ 'yscrollcommand' ] = self.scrollbar.set
        self.scrollbar.pack( side='right', fill='y' )
        self.text.pack(side='left', expand=True, fill='both')

        self.filename = filename
        self.saved = ''
        if filename and os.path.isfile( filename ): self.load( filename )
        else: self.settext( text )
        self.parent = parent
        self.latest = None
        self.check_autosave()
    def undo( self, event=None ):
        try: self.text.edit_undo()
        except: pass
    def redo( self, event=None ):
        try: self.text.edit_redo()
        except: pass
    def active( self, event=None ): self.latest = time.time()
    def check_autosave( self ): # check every 500 msec: if there is new activity, and the latest activity occurred more than 2s ago, then call autosave()
        if self.latest != None and time.time() - self.latest > 2.0: self.autosave(); self.latest = None
        self.after_id = self.after( 500, self.check_autosave )
    def autosave( self ):
        if self.filename == None: return
        text = self.gettext()
        if text == self.saved: return
        encoded = text.encode( 'utf-8' )
        open( self.filename, 'wt' ).write( encoded )
        self.text.edit_separator()
        self.saved = text
    def destroy( self ):
        self.after_cancel( self.after_id )
        self.autosave()
        tkinter.Frame.destroy( self )
    def load( self, filename ):
        self.autosave()
        text = open( filename, 'rt' ).read().decode( 'utf-8' )
        self.saved = text
        self.filename = filename
        self.settext( text )
    def settext( self, text='' ):
        self.text.delete( '1.0', 'end' )
        self.text.insert( '1.0', text )
        self.text.mark_set( 'insert', 'end' )
        self.text.edit_reset()
        self.text.focus()
        self.active()
    def append( self, text, ensure_newline_first=False ):
        self.text.edit_separator()
        if ensure_newline_first and self.text.get( 'end-2c', 'end-1c' ) != '\n': text = '\n' + text
        self.text.insert( 'end', text )
        self.text.mark_set( 'insert', 'end' )
        self.text.see( 'end' )
        self.active()
    def gettext( self ):
        return self.text.get( '1.0', 'end-1c' )




class STAnalysisWindow( Dialog, TkMPL):

    """
    An analysis tool for Stimulus Test so we can check multiple stimulation sites
    Will only be active if using the DS5 as it uses data stored in stimGUI
    """
    #TODO: Remove this dependency

    def __init__(self, parent, mode, geometry=None, modal=True):

        self.mode = mode
        self.parent = parent
        self.channel = 0  # first EMG channel
        self.data = parent.data[mode]
        self.HReflexData = [] #this will store the data
        self.PopulateData()
        TkMPL.__init__(self)

        if geometry == 'parent': geometry = parent.geometry()
        else: geometry = '1000x400'

        Dialog.__init__(self, parent=parent, title='%s Analysis' % parent.modenames[mode],
                        icon=os.path.join(GUIDIR, 'epocs.ico'), geometry=geometry, blocking=not DEVEL, modal=modal)

    def buttonbox(self):  # override default OK + cancel buttons (and <Return> key binding)
        """
        No standard OK/cancel buttons.
        """
        pass

    def PopulateData(self):

        if hasattr(self.parent,'stimGUI'): idx = self.parent.stimGUI.DataIdx
        else: idx =[]
        if idx == []: None
        else:
            for trial,run in idx:
                self.HReflexData.append(self.data[trial][run])


    def body(self, frame):
        bg = 'gray80'
        TableHeader  = tkinter.Frame(frame,bd=1,bg=bg)
        SubFrame = tkinter.Frame(TableHeader,bg=bg)
        FigureHeader = tkinter.Frame(frame,bd=1,bg=bg)

        self.axiscontrollers_emg1 = []

        figure, widget, container = self.NewFigure(parent=FigureHeader, prefix='overlay', suffix='main', width=500,
                                                   height=300)
        axes = self.overlay_axes_main = figure.gca()

        self.overlay = ResponseOverlay(
            data=self.HReflexData, channel=self.channel,
            fs=self.parent.fs, lookback=self.parent.lookback,
            axes=axes, color=self.colors['emg%d' % (self.channel + 1)],
            responseInterval=None, comparisonInterval=None,
            prestimulusInterval=None,
            updateCommand=None,
        )

        x = self.parent.operator.params._TraceLimitVolts[self.channel];
        self.overlay.yController.set([-x, x])
        self.axiscontrollers_emg1.append(self.overlay.yController)
        self.widgets.overlay_yadjust = PlusMinusTk(parent=FigureHeader, controllers=self.axiscontrollers_emg1).place(
            in_=widget, width=20, height=40, relx=0.93, rely=0.25, anchor='w')
        self.widgets.overlay_xadjust = PlusMinusTk(parent=FigureHeader, controllers=self.overlay.xController).place(
            in_=widget, width=40, height=20, relx=0.92, rely=0.05, anchor='se')

        headings = ['Location','Amplitude(mA)']
        DictList = self.parent.stimGUI.StimLocations
        self.tree = TableButton(List=DictList,parent=self,overlay=self.overlay,Headings=headings,Frame=SubFrame,ButtonHeader='Plot')

        TableHeader.rowconfigure(0, weight=1)
        TableHeader.columnconfigure(0, weight=1)
        FigureHeader.rowconfigure(0, weight=1)
        FigureHeader.columnconfigure(0, weight=1)

        self.PlotAllButton = tkinter.Button(SubFrame,text='Plot All',command=self.PlotAll)
        self.PlotAllButton.grid(column=1,row=1,sticky='s')

        self.ClearAllButton = tkinter.Button(SubFrame, text='Clear Plot', command=self.ClearPlot)
        self.ClearAllButton.grid(column=2,row=1,sticky='s')



        container.place(relx=0.5,rely=0.5,anchor='center')#grid(row=0, column=0, sticky='nsew', padx=5, pady=2)
        SubFrame.place(relx=0.5,rely=0.5,anchor='center')
        TableHeader.pack(side='left', fill='both', expand='y')
        FigureHeader.pack(side='right', fill='both', expand='y')

    def PlotAll(self):
        #for item in self.tree.get_children():
        self.tree.ToggleAll(YES=True)
        return

    def ClearPlot(self):
        #for item in self.tree.get_children():
        self.tree.ToggleAll(YES=False)
        return



class AnalysisWindow( Dialog, TkMPL ):
    """
    An AnalysisWindow is created as a modal Dialog() when the "Analysis" button is
    pressed on the vc, rc, ct or tt tab of the GUI().

    If DEVEL is True (i.e. if this file was run with the --devel flag) then the
    AnalysisWindow instance is available as the .child attribute of the parent GUI()
    or OfflineAnalysis() instance, and the constructor will not block.
    """
    def __init__( self, parent, mode, geometry=None, modal=True, online=True ):
        """
        AnalysisWindow constructor

        <parent>   : the GUI or OfflineAnalysis instance that created this
        <mode>     : 'vc', 'rc', 'ct', 'tt' or 'offline'
        <geometry> : an optional TkInter geometry string that is passed through to the
                     Dialog superclass constructor
        <modal>    : passed through to the Dialog superclass constructor
        <online>   : True in the context of a GUI, False for an OfflineAnalysis (in the
                     latter case, Up-Condition and Down-Condition buttons are not created).
        """
        self.mode = mode
        self.channel = 0 # first EMG channel
        self.data = parent.data[ mode ]
        self.parent = parent

        #Sort the data if we have currents, and use the currents in the ResponseSequence
        if online==True:
            if hasattr(self.parent,'stimGUI'): c = parent.stimGUI.CurrentAmplitudeState
            else: c = []
            DS5 = int(self.parent.operator.remote.GetParameter('EnableDS5ControlFilter'))
        else:
            if parent.Currents != []:
                c = parent.Currents
                DS5 = 1
            else: DS5=0; c= []

        self.StimPool = 1

        if c != [] and DS5==1: #if no DS5 then don't do this, it will cause more problems than good

            if (mode in ['rc','offline']):
                cosrted = sorted(c)
                if cosrted[0] > 50: self.Currents = ['{:.3f}'.format(i/1000) for i in cosrted]
                else: self.Currents = ['{:.3f}'.format(i) for i in cosrted]
                cindx = sorted(range(len(c)), key=lambda k: c[k])
                #Need to refine this for pooled data
                data_sorted = [self.data[k] for k in cindx]
                self.data = data_sorted
            else:
                if c[0] > 50: self.Currents = ['{:.3f}'.format(i/1000) for i in c]
                else: self.Currents = ['{:.3f}'.format(i) for i in c]
        else: self.Currents = []

        self.description = parent.GetDescription( mode )
        self.acceptMode = None
        self.online = online
        TkMPL.__init__( self )
        if geometry == 'parent': geometry = parent.geometry()
        Dialog.__init__( self, parent=parent, title='%s Analysis' % parent.modenames[ mode ], icon=os.path.join( GUIDIR, 'epocs.ico' ), geometry=geometry, blocking=not DEVEL, modal=modal )
        # NB: if blocking=True, Dialog.__init__ will not return until the dialog is destroyed
        if DEVEL: self.parent.child = self  # only do this during DEVEL because it creates a mutual reference loop and hence a memory leak

    def buttonbox( self ): # override default OK + cancel buttons (and <Return> key binding)
        """
        No standard OK/cancel buttons.
        """
        pass

    def ok_down( self, event=None ): self.acceptMode = 'down'; self.ok()
    def ok_up( self, event=None ): self.acceptMode = 'up'; self.ok()

    def cancel( self, event=None ):
        try: self.parent.after_cancel( self.after_id )
        except: pass
        controllers = self.parent.axiscontrollers_emg1
        if hasattr( self, 'overlay' ) and self.overlay.yController in controllers: controllers.remove( self.overlay.yController )
        for x in self.MatchArtists( 'figure' ): matplotlib.pyplot.close( x )
        Dialog.cancel( self )

    def TimingsSaved( self ):
        """
        Check whether the timings (i.e. endpoints of the prestimulus, reference and target
        response interval selectors) have been remembered (stored in self.parent.operator.params)
        by pressing the "Use Marked Timings" button. Return True or False accordingly.
        """
        result = True
        params = self.parent.operator.params
        def equal( a, b ): return float( '%g' % a ) == float( '%g' % b )
        if self.overlay.responseSelector:
            start, end = [ sec * 1000.0 for sec in self.overlay.responseSelector.get() ]
            if not equal( params._ResponseStartMsec[ 0 ], start ) or not equal( params._ResponseEndMsec[ 0 ], end ): result = False
        if self.overlay.comparisonSelector:
            start, end = [ sec * 1000.0 for sec in self.overlay.comparisonSelector.get() ]
            if not equal( params._ComparisonStartMsec[ 0 ], start ) or not equal( params._ComparisonEndMsec[ 0 ], end ): result = False
        if self.overlay.prestimulusSelector:
            start, end = [ sec * 1000.0 for sec in self.overlay.prestimulusSelector.get() ]
            if not equal( params._PrestimulusStartMsec[ 0 ], start ) or not equal( params._PrestimulusEndMsec[ 0 ], end ): result = False
        return result

    def PersistTimings( self ):
        """
        Store timing information from the ResponseOverlay object self.overlay.  This
        information consists of the endpoints of the prestimulus, reference and target
        response interval selectors. Store them in self.parent.operator.params
        This is called when the "Use Marked Timings" button is pressed.
        """
        if self.overlay.prestimulusSelector:
            start, end = [ sec * 1000.0 for sec in self.overlay.prestimulusSelector.get() ]
            self.parent.operator.Set( _PrestimulusStartMsec=[ start, start ], _PrestimulusEndMsec=[ end, end ] )
            self.parent.Log( 'Updated pre-stimulus interval: %g to %g msec' % ( start, end ) )
        if self.overlay.comparisonSelector:
            start, end = [ sec * 1000.0 for sec in self.overlay.comparisonSelector.get() ]
            self.parent.operator.Set( _ComparisonStartMsec=[ start, start ], _ComparisonEndMsec=[ end, end ] )
            self.parent.Log( 'Updated reference response interval: %g to %g msec' % ( start, end ) )
        if self.overlay.responseSelector:
            start, end = [ sec * 1000.0 for sec in self.overlay.responseSelector.get() ]
            self.parent.operator.Set( _ResponseStartMsec=[ start, start ], _ResponseEndMsec=[ end, end ] )
            self.parent.Log( 'Updated target response interval: %g to %g msec' % ( start, end ) )
        self.UpdateResults()

    def apply( self ):
        """
        Called by the superclass Dialog.ok() method, which in turn is called by either
        ok_up() or ok_down() when the "Up-Condition" or "Down-Condition" button is pressed.
        """
        params = self.parent.operator.params
        factor = self.parent.operator.GetVolts( 1 )
        if self.acceptMode == 'up':
            info = self.distribution.panel.uptarget
            critical = float( info.value ) / factor
            critical = float( info.fmt % critical )
            lims = ( critical, None )
        if self.acceptMode == 'down':
            info = self.distribution.panel.downtarget
            critical = float( info.value ) / factor
            critical = float( info.fmt % critical )
            lims = ( 0, critical )
        if self.acceptMode != None:
            if self.parent.operator.params._ResponseBarLimit < critical or self.parent.operator.params._BaselineResponse == None:
                self.parent.operator.Set( _ResponseBarLimit=critical * 2 )
            self.parent.operator.Set( _ResponseMin=[ lims[ 0 ], params._ResponseMin[ 1 ] ] )
            self.parent.operator.Set( _ResponseMax=[ lims[ 1 ], params._ResponseMax[ 1 ] ] )
            self.parent.SetBarLimits( 'tt' )
            self.parent.SetTargets( 'tt' )

            direction = { 'up' : 'Upward', 'down' : 'Downward' }.get( self.acceptMode )
            preposition = { 'up' : 'above', 'down' : 'below' }.get( self.acceptMode )
            start, end = [ sec * 1000.0 for sec in self.overlay.responseSelector.get() ]
            self.parent.operator.Set( _ResponseStartMsec=[ start, start ], _ResponseEndMsec=[ end, end ] )
            self.parent.Log( '%s conditioning target set: %g-%g msec response will be rewarded %s %s%s' % ( direction, start, end, preposition, critical, self.parent.operator.params._VoltageUnits ) )

    def body( self, frame ):
        """
        Construct the Tk widgets and matplotlib artists that make up the analysis window.
        """
        frame[ 'bg' ] = self.colors.bg

        figwidth, figheight = 0.75 * self.winfo_screenwidth(), 0.75 * self.winfo_screenheight()
        figreducedwidth = figwidth * 0.8
        fighalfheight = figheight * 0.5 - 50

        if self.mode in [ 'vc' ]:
            header = self.widgets.overlay_frame_header = tkinter.Frame( frame, bg=self.colors.progress )
            w = self.widgets.mvc_button_log = tkinter.Button( header, text='Log Results', command=Curry( self.Log, type='mvc' ) ); w.pack( side='right' )

            figure, widget, container = self.NewFigure( parent=frame, prefix='an', suffix='main', width=figwidth, height=figheight )
            self.mvc = MVC( self.data, fs=float( self.parent.fs ) / self.parent.sbs, callback=self.Changed )
            self.widgets.an_xadjust_mvc = PlusMinusTk( frame, controllers=self.mvc.xcon ).place( in_=widget, relx=0.92, rely=0.06, width=40, height=20, anchor='se' )

            header.grid( row=1, column=1, sticky='nsew', padx=5, pady=2 )
            container.grid( row=2, column=1, sticky='nsew', padx=5, pady=2 )
            frame.grid_rowconfigure( 2, weight=1 )
            frame.grid_columnconfigure( 1, weight=1 )

        elif self.mode in [ 'rc', 'ct', 'tt', 'offline', 'mixed' ]:

            uppernb = self.MakeNotebook( parent=self, name='notebook_upper' )
            uppernb.pack( side='top', fill='both', expand=1 )
            tabframe = self.AddTab( 'overlay', 'Timings', nbname='notebook_upper' )
            tabframe.grid( row=1, column=1, sticky='nsew' ); tabframe.master.grid_rowconfigure( 1, weight=1 ); tabframe.master.grid_columnconfigure( 1, weight=1 )

            header = self.widgets.overlay_frame_header = tkinter.Frame( tabframe, bg=self.colors.progress )
            switch = Switch( header, title='Rectification: ', offLabel='off', onLabel='on', initialValue=0, command=self.UpdateLines )
            switch.pack( side='left', pady=3 )
            tkinter.Frame( header, bg=header[ 'bg' ] ).pack( side='left', padx=25 )
            button = self.widgets.overlay_button_savetimings = tkinter.Button( header, text='Use marked timings', command=self.PersistTimings )
            button.pack( side='right', pady=3 )

            figure, widget, container = self.NewFigure( parent=tabframe, prefix='overlay', suffix='main', width=figwidth, height=fighalfheight )
            axes = self.overlay_axes_main = figure.gca()
            responseInterval    = self.parent.operator.params._ResponseStartMsec[ self.channel ] / 1000.0, self.parent.operator.params._ResponseEndMsec[ self.channel ] / 1000.0
            comparisonInterval  = self.parent.operator.params._ComparisonStartMsec[ self.channel ] / 1000.0, self.parent.operator.params._ComparisonEndMsec[ self.channel ] / 1000.0
            prestimulusInterval = self.parent.operator.params._PrestimulusStartMsec[ self.channel ] / 1000.0, self.parent.operator.params._PrestimulusEndMsec[ self.channel ] / 1000.0
            #if self.mode not in [ 'rc' ]: comparisonInterval = prestimulusInterval = None
            self.overlay = ResponseOverlay(
                data=self.data, channel=self.channel,
                fs=self.parent.fs, lookback=self.parent.lookback,
                axes=axes, color=self.colors[ 'emg%d' % ( self.channel + 1 ) ],
                responseInterval=responseInterval, comparisonInterval=comparisonInterval, prestimulusInterval=prestimulusInterval,
                updateCommand=self.Changed,
            )
            if len( self.parent.axiscontrollers_emg1 ): self.overlay.yController.set( self.parent.axiscontrollers_emg1[ -1 ].get() )
            else: x = self.parent.operator.params._TraceLimitVolts[ self.channel ]; self.overlay.yController.set( [ -x, x ] )
            self.parent.axiscontrollers_emg1.append( self.overlay.yController )
            self.widgets.overlay_yadjust = PlusMinusTk( parent=tabframe, controllers=self.parent.axiscontrollers_emg1 ).place( in_=widget, width=20, height=40, relx=0.93, rely=0.25, anchor='w' )
            self.widgets.overlay_xadjust = PlusMinusTk( parent=tabframe, controllers=self.overlay.xController         ).place( in_=widget, width=40, height=20, relx=0.92, rely=0.05, anchor='se' )

            #header.pack( side='top', fill='both', expand=1 )
            #container.pack( fill='both', expand=1 )
            header.grid( row=1, column=1, sticky='nsew', padx=5, pady=2 )
            container.grid( row=2, column=1, sticky='nsew', padx=5, pady=2 )
            tabframe.grid_rowconfigure( 2, weight=1 )
            tabframe.grid_columnconfigure( 1, weight=1 )


            lowernb = self.MakeNotebook( parent=self, name='notebook_lower' )
            lowernb.pack( side='top', fill='both', expand=1 )

            if self.mode in [ 'rc', 'ct', 'tt', 'offline', 'mixed' ]:
                tabframe = self.AddTab( 'sequence', 'Sequence', nbname='notebook_lower' )

                header = self.widgets.sequence_frame_header = tkinter.Frame( tabframe, bg=self.colors.progress )
                tkinter.Label( header, text='Trials to pool: ', bg=header[ 'bg' ] ).pack( side='left', padx=3, pady=3 )
                vcmd = ( self.register( self.PoolingEntry ), '%s', '%P' )
                entry = self.widgets.sequence_entry_pooling = tkinter.Entry( header, width=2, validate='key', validatecommand=vcmd, textvariable=tkinter.Variable( header, value='1' ), bg='#FFFFFF' )
                entry.pack( side='left', padx=3, pady=3 )
                switch = self.widgets.sequence_switch_responsemode = Switch( header, offLabel='mean rect.', onLabel='peak-to-peak', command=self.UpdateResults )
                switch.pack( side='left', pady=3, padx=10 )
                w = self.widgets.sequence_button_log = tkinter.Button( header, text='Log Results', command=Curry( self.Log, type='sequence' ) ); w.pack( side='right' )

                figure, widget, container = self.NewFigure( parent=tabframe, prefix='sequence', suffix='main', width=figreducedwidth, height=fighalfheight )
                panel = tkinter.Frame( tabframe, bg=tabframe[ 'bg' ] )
                self.sequence = ResponseSequence( self.overlay, pooling=1, tk=panel, p2p=False ,xlabels=self.Currents)
                cid = self.sequence.axes.figure.canvas.mpl_connect( 'button_press_event', self.ToggleTrial )

                #header.pack( side='top', fill='both', expand=1 )
                #container.pack( fill='both', expand=1 )
                header.grid( row=1, column=1, columnspan=2, sticky='nsew', padx=5, pady=2 )
                container.grid( row=2, column=1, sticky='nsew', padx=5, pady=2 )
                panel.grid( row=2, column=2, sticky='ns', padx=5, pady=2 )
                tabframe.grid_rowconfigure( 2, weight=1 )
                tabframe.grid_columnconfigure( 1, weight=1 )

                tabframe.pack( fill='both', expand=1 )


            if self.mode in [ 'ct', 'tt', 'offline', 'mixed' ]:
                tabframe = self.AddTab( 'distribution', 'Distribution', nbname='notebook_lower' )

                header = self.widgets.distribution_frame_header = tkinter.Frame( tabframe, bg=self.colors.progress )
                w = self.widgets.distribution_button_log = tkinter.Button( header, text='Log Results', command=Curry( self.Log, type='distribution' ) ); w.pack( side='right' )
                #conditioning = tkinter.Frame( self, bg=header[ 'bg' ] )
                #w = self.widgets.distribution_button_upcondition = tkinter.Button( conditioning, text="Up-Condition", width=10, command=self.ok_up ); w.pack( side='top', pady=2, ipadx=16, fill='both', expand=1 )
                #w = self.widgets.distribution_button_downcondition = tkinter.Button( conditioning, text="Down-Condition", width=10, command=self.ok_down ); w.pack( side='bottom', pady=2, ipadx=16, fill='both', expand=1 )
                ##conditioning.place( in_=self.widgets.overlay_button_savetimings, anchor='ne', relx=1.0, rely=1.1 )
                #conditioning.place( in_=tabframe, anchor='se', relx=1.0, rely=1.0 )

                figure, widget, container = self.NewFigure( parent=tabframe, prefix='distribution', suffix='main', width=figreducedwidth, height=fighalfheight )
                panel = tkinter.Frame( tabframe, bg=tabframe[ 'bg' ] )
                self.distribution = ResponseDistribution( self.overlay, targetpc=self.parent.operator.params._TargetPercentile, nbins=10, tk=panel )
                vcmd = ( self.register( self.TargetPCEntry ), '%s', '%P' )
                self.distribution.entry.widgets.value.configure( width=3, validatecommand=vcmd, validate='key' )

                w = self.widgets.distribution_button_upcondition   = tkinter.Button( self.distribution.frame, text="Up-Condition",   width=10, command=self.ok_up   )
                if self.online: w.grid( row=6, column=3, sticky='nsew', padx=1, pady=1, ipadx=16 )
                w = self.widgets.distribution_button_downcondition = tkinter.Button( self.distribution.frame, text="Down-Condition", width=10, command=self.ok_down )
                if self.online: w.grid( row=7, column=3, sticky='nsew', padx=1, pady=1, ipadx=16 )

                #header.pack( side='top', fill='both', expand=1 )
                #container.pack( fill='both', expand=1 )
                header.grid( row=1, column=1, columnspan=2, sticky='nsew', padx=5, pady=2 )
                container.grid( row=2, column=1, sticky='nsew', padx=5, pady=2 )
                panel.grid( row=2, column=2, sticky='ns', padx=5, pady=2 )
                tabframe.grid_rowconfigure( 2, weight=1 )
                tabframe.grid_columnconfigure( 1, weight=1 )

                tabframe.pack( fill='both', expand=1 )
                self.SelectTab( 'distribution', 'notebook_lower' )


        self.UpdateResults()
        self.DrawFigures()
        self.latest = None
        self.CheckUpdate()

    def ToggleTrial( self, event ):
        """
        Callback registered as the matplotlib mouse-button-press event handler for any analysis
        window that implements a ResponseSequence object. Allows highlighting to be toggled
        with the left mouse button, and removal with the right button.
        """
        if not hasattr( self, 'sequence' ): return
        if event.inaxes != self.sequence.axes or event.button not in [ 1, 3 ]: return
        where = round( event.xdata )
        rounded = int( self.sequence.pooling * round( where / self.sequence.pooling ) )
        if abs( where - rounded ) > 0.1: return
        if rounded not in range( self.sequence.pooling, self.sequence.n + 1, self.sequence.pooling ): return
        indices = range( rounded - self.sequence.pooling, rounded )
        wasNormal = sum( [ self.overlay.emphasis[ index ] != 0 for index in indices ] ) == 0
        if wasNormal:
            if event.button == 1: newValue = +1
            else:                 newValue = -1
        else: newValue = 0
        for index in indices: self.overlay.emphasis[ index ] = newValue
        self.UpdateResults()
        return False

    def UpdateLines( self, rectified=False ):
        """
        Callback for the "mean rect." vs "peak-to-peak" switch: re-draws the ResponseOverlay
        according to the current switch setting.
        """
        self.overlay.Update( rectified=rectified )
        self.DrawFigures()

    def Changed( self, *pargs ):
        """
        Flag that something has changed and needs updating
        """
        self.latest = time.time()

    def CheckUpdate( self ):
        """
        Check every 100 msec: if there is new activity flagged by Changed(), and the latest
        activity occurred more than 2s ago, then call UpdateResults().
        This function renews its own schedule using Tk.after().  The initial scheduling
        is done by an explicit call to CheckUpdate() in body()
        """
        if self.latest != None and time.time() - self.latest > 0.5: self.UpdateResults(); self.latest = None
        self.after_id = self.parent.after( 100, self.CheckUpdate )

    def PoolingEntry( self, oldValue, newValue ):
        # TODO:  only got this far with method-by-method docstrings
        if len( newValue ) == 0: return True
        if newValue == oldValue: return True
        try: val = float( newValue )
        except: return False
        if val != round( val ): return False
        if val < 1: return False
        if val > len( self.overlay.data ): return False
        self.Changed()
        return True

    def UpdateResults( self, *unused_args ):
        if hasattr( self, 'mvc' ):
            self.mvc.Update()
        if hasattr( self, 'sequence' ):
            pooling = self.widgets.sequence_entry_pooling.get()
            try: pooling = int( pooling )
            except: pooling = None # no change
            p2p = self.widgets.sequence_switch_responsemode.scale.get()
            self.sequence.Update( pooling=pooling, p2p=p2p ,xlabels=self.Currents)
        if hasattr( self, 'distribution' ):
            targetpc = self.distribution.entry.widgets.value.get()
            try: targetpc = float( targetpc )
            except: targetpc = None
            self.distribution.Update( targetpc=targetpc )
            EnableWidget( [ self.widgets.distribution_button_upcondition, self.widgets.distribution_button_downcondition ], self.TimingsSaved() )
        if hasattr( self, 'overlay' ):
            self.overlay.Update()
            if self.TimingsSaved(): self.widgets.overlay_button_savetimings.configure( state='disabled', bg=self.colors.button )
            else:                   self.widgets.overlay_button_savetimings.configure( state='normal',   bg='#FF4444' )
        ax = self.artists.get( 'overlay_axes_main', None )
        if ax: matplotlib.pyplot.figure( ax.figure.number ).sca( ax )
        self.DrawFigures()
        for button in self.MatchWidgets( 'button', 'log' ): button[ 'state' ] = 'normal'
        for pm in self.MatchWidgets( 'xadjust', 'mvc' ): pm.Draw()

    def Log( self, type ):
        self.parent.Log( '===== %s Analysis (%s) =====' % ( self.parent.modenames[ self.mode ], self.description ) )
        if type == 'mvc':
            start, end = [ sec * 1000.0 for sec in self.mvc.selector.get() ]
            if self.mvc.estimate != None: self.parent.Log( 'MVC estimated at %s over a %g-msec window' % ( self.mvc.estimate, end - start ) )
        elif type == 'sequence':
            removed = [ str( ind + 1 ) for ind, emph in enumerate( self.overlay.emphasis ) if emph < 0 ]
            if len( removed ): self.parent.Log( 'Trials removed before analysis: #%s' % ','.join( removed ) )
            used = self.sequence.n - len( removed )
            if self.sequence.p2p: metric = 'peak-to-peak'
            else: metric = 'average rectified signal'
            self.parent.Log( 'From %d measurements, pooled in groups of %d:' % ( used, self.sequence.pooling ) )
            start, end = [ sec * 1000.0 for sec in self.overlay.prestimulusSelector.get() ]
            meanPrestim = self.sequence.panel.bg.str()
            self.parent.Log( '   Mean pre-stimulus activity (%g to %g msec) = %s (%s)' % ( start, end, meanPrestim, metric ) )
            start, end = [ sec * 1000.0 for sec in self.overlay.comparisonSelector.get() ]
            maxComparison = self.sequence.panel.mmax.str()
            self.parent.Log( '   Maximum reference response (%g to %g msec) = %s (%s)' % ( start, end, maxComparison, metric ) )
            start, end = [ sec * 1000.0 for sec in self.overlay.responseSelector.get() ]
            maxResponse = self.sequence.panel.hmax.str()
            self.parent.Log( '   Maximum target response (%g to %g msec) = %s (%s)\n' % ( start, end, maxResponse, metric ) )
        elif type == 'distribution':
            start, end = [ sec * 1000.0 for sec in self.overlay.responseSelector.get() ]
            removed = [ str( ind + 1 ) for ind, emph in enumerate( self.overlay.emphasis ) if emph < 0 ]
            if len( removed ): self.parent.Log( 'Trials removed before analysis: #%s' % ','.join( removed ) )
            self.parent.Log( 'From %s trials using target response interval from %g to %gmsec and aiming at percentile %s: ' % ( self.distribution.panel.n.str(), start, end, self.distribution.entry.str() ) )
            self.parent.Log( '   pre-stimulus activity (median, mean) = %s' % self.distribution.panel.prestimulus.str() )
            self.parent.Log( '   reference response    (median, mean) = %s' % self.distribution.panel.comparison.str() )
            self.parent.Log( '   target response       (median, mean) = %s' % self.distribution.panel.response.str() )
            self.parent.Log( '   upward target = %s' % self.distribution.panel.uptarget.str() )
            self.parent.Log( '   downward target = %s\n' % self.distribution.panel.downtarget.str() )
            if self.mode in [ 'ct' ] and self.parent.operator.params._BaselineResponse == None:
                info = self.distribution.panel.response
                baselines = self.parent.operator.params._EarlyLoggedCTBaselines
                baselines[ self.parent.operator.LastRunNumber( mode=self.mode ) ] = info.value[ 0 ]
                meanOfMedians = sum( baselines.values() ) / float( len( baselines ) )
                self.parent.Log( 'Estimated baseline so far = %s    *****\n' % info.str( meanOfMedians ) )
            if self.mode in ['tt']:
                successCounter = self.parent.widgets.get('tt_label_value_success', None)
                self.parent.Log('Training Trial (%s) success percentage = %s' % (self.description, successCounter['text']))
        else: self.parent.Log( '??? - unexpected logging error (type "%s")' % type )
        for button in self.MatchWidgets( type, 'button', 'log' ): button[ 'state' ] = 'disabled'

    def TargetPCEntry( self, oldValue, newValue ):
        if len( newValue ) == 0: return True
        if newValue == oldValue: return True
        try: val = float( newValue )
        except: return False
        if val < 0 or val > 100: return False
        self.Changed()
        self.parent.operator.params._TargetPercentile = val
        return True



class SettingsWindow( Dialog, TkMPL ):
    """
    A Dialog subclass implementing the window that opens when the "Settings" button is
    pressed.
    """
    def __init__( self, parent, mode ):
        self.mode = mode
        self.parent = parent
        TkMPL.__init__( self )
        Dialog.__init__( self, parent=parent, title='Settings', icon=os.path.join( GUIDIR, 'epocs.ico' ) )

    def body( self, frame ):

        bg = frame['bg']
        self.MakeNotebook().pack(expand=1, fill='both', padx=5, pady=5, side='top')
        EMGframe = self.AddTab('EMGsettings', title='EMG')
        EMGframe['bg'] = bg
        params = self.parent.operator.params
        units = params._VoltageUnits
        warningCommand = (self.register(self.ValueWarnings), '%W', '%P')

        # EMG parameters
        state = {True: 'normal', False: 'disabled'}[self.mode in ['vc']]
        section = tkinter.LabelFrame(EMGframe, text='Feedback Bars', bg=bg)
        self.widgets.entry_backgroundbar = LabelledEntry(section,
                                                         'Voluntary Contraction\naxes limit (%s)\n' % units).connect(
            params, '_VCBackgroundBarLimit').enable(state).grid(row=1, column=1, sticky='e', padx=8, pady=8)
        state = {True: 'normal', False: 'disabled'}[self.mode in ['vc', 'rc', 'ct', 'tt']]
        self.widgets.entry_refresh = LabelledEntry(section, 'Bar refresh\ncycle (msec)').connect(params,
                                                                                                 '_BarUpdatePeriodMsec').enable(
            state).grid(row=2, column=1, sticky='e', padx=8, pady=8)
        state = {True: 'normal', False: 'disabled'}[self.mode in ['tt']]
        w = self.widgets.entry_responsebar = LabelledEntry(section, 'Response bar\naxes limit (%s)' % units).connect(
            params, '_ResponseBarLimit').enable(state).grid(row=1, column=2, sticky='e', padx=8, pady=8)
        w.entry.configure(validatecommand=warningCommand, validate='key')
        w = self.widgets.entry_baselineresponse = LabelledEntry(section, 'Baseline\nresponse (%s)' % units).connect(
            params, '_BaselineResponse').enable(state).grid(row=2, column=2, sticky='e', padx=8, pady=8)
        w.entry.configure(validatecommand=warningCommand, validate='key')
        section.pack(side='top', pady=10, padx=10, fill='both')

        state = {True: 'normal', False: 'disabled'}[self.mode in ['rc', 'ct', 'tt']]
        fbswitchstate = {True: 'normal', False: 'disabled'}[self.mode in ['vc', 'rc', 'ct', 'tt']]
        section = tkinter.LabelFrame(EMGframe, text='Background EMG', bg=bg)
        subsection = tkinter.Frame(section, bg=bg)
        tkinter.Label(subsection, text='Background EMG', justify='right', state=state, bg=bg).grid(row=1, column=1,
                                                                                                   sticky='nsw', padx=2,
                                                                                                   pady=2)
        tkinter.Label(subsection, text='EMG 1', justify='center', state=state, bg=bg).grid(row=1, column=2,
                                                                                           sticky='nsew', padx=10,
                                                                                           pady=2)
        tkinter.Label(subsection, text='EMG 2', justify='center', state=state, bg=bg).grid(row=1, column=3,
                                                                                           sticky='nsew', padx=10,
                                                                                           pady=2)
        tkinter.Label(subsection, text='Min. (%s)' % units, justify='right', state=state, bg=bg).grid(row=2, column=1,
                                                                                                      sticky='nse',
                                                                                                      padx=2, pady=2)
        tkinter.Label(subsection, text='Max. (%s)' % units, justify='right', state=state, bg=bg).grid(row=3, column=1,
                                                                                                      sticky='nse',
                                                                                                      padx=2, pady=2)
        self.widgets.entry_bgmin1 = LabelledEntry(subsection, '').connect(params, '_BackgroundMin', 0).enable(
            state).grid(row=2, column=2, sticky='nsew', padx=2, pady=2)
        self.widgets.entry_bgmax1 = LabelledEntry(subsection, '').connect(params, '_BackgroundMax', 0).enable(
            state).grid(row=3, column=2, sticky='nsew', padx=2, pady=2)
        self.widgets.entry_bgmin2 = LabelledEntry(subsection, '').connect(params, '_BackgroundMin', 1).enable(
            state).grid(row=2, column=3, sticky='nsew', padx=2, pady=2)
        self.widgets.entry_bgmax2 = LabelledEntry(subsection, '').connect(params, '_BackgroundMax', 1).enable(
            state).grid(row=3, column=3, sticky='nsew', padx=2, pady=2)

        subsection.pack(fill='x', padx=10, pady=10)
        ch = params._EMGChannelNames
        self.widgets.switch_fbchannel = Switch(section, title='Feedback from:    ', offLabel=ch[0], onLabel=ch[1],
                                               values=ch, initialValue=params._FeedbackChannel).connect(params,
                                                                                                        '_FeedbackChannel').enable(
            fbswitchstate).pack(side='left', padx=10, pady=10)
        self.widgets.entry_hold = LabelledEntry(section, 'Background hold\nduration (sec)').connect(params,
                                                                                                    '_BackgroundHoldSec').enable(
            state).pack(padx=10, pady=10)
        section.pack(side='top', pady=10, padx=10, fill='both')

        state = {True: 'normal', False: 'disabled'}[self.mode in ['tt']]
        section = tkinter.LabelFrame(EMGframe, text='Responses', bg=bg)
        subsection = tkinter.Frame(section, bg=bg)
        self.widgets.entry_rstart = LabelledEntry(subsection, 'Response interval: ').connect(params,
                                                                                             '_ResponseStartMsec',
                                                                                             '*').enable(state).pack(
            side='left', padx=3)
        self.widgets.entry_rend = LabelledEntry(subsection, u'\u2013').connect(params, '_ResponseEndMsec', '*').enable(
            state).pack(side='left', padx=3)
        tkinter.Label(subsection, text=' msec', justify='left', state=state, bg=bg).pack(side='left', padx=3)
        subsection.pack(fill='x', padx=10, pady=10)
        subsection = tkinter.Frame(section, bg=bg)
        tkinter.Label(subsection, text='Reward Ranges', justify='left', state=state, bg=bg).grid(row=1, column=1,
                                                                                                 sticky='nsw', padx=2,
                                                                                                 pady=2)
        tkinter.Label(subsection, text='EMG 1', justify='center', state=state, bg=bg).grid(row=1, column=2,
                                                                                           sticky='nsew', padx=10,
                                                                                           pady=2)
        tkinter.Label(subsection, text='EMG 2', justify='center', state=state, bg=bg).grid(row=1, column=3,
                                                                                           sticky='nsew', padx=10,
                                                                                           pady=2)
        tkinter.Label(subsection, text='Min. (%s)' % units, justify='right', state=state, bg=bg).grid(row=2, column=1,
                                                                                                      sticky='nse',
                                                                                                      padx=2, pady=2)
        tkinter.Label(subsection, text='Max. (%s)' % units, justify='right', state=state, bg=bg).grid(row=3, column=1,
                                                                                                      sticky='nse',
                                                                                                      padx=2, pady=2)
        self.widgets.entry_rmin1 = LabelledEntry(subsection, '').connect(params, '_ResponseMin', 0).enable(state).grid(
            row=2, column=2, sticky='nsew', padx=2, pady=2)
        self.widgets.entry_rmax1 = LabelledEntry(subsection, '').connect(params, '_ResponseMax', 0).enable(state).grid(
            row=3, column=2, sticky='nsew', padx=2, pady=2)
        self.widgets.entry_rmin2 = LabelledEntry(subsection, '').connect(params, '_ResponseMin', 1).enable(state).grid(
            row=2, column=3, sticky='nsew', padx=2, pady=2)
        self.widgets.entry_rmax2 = LabelledEntry(subsection, '').connect(params, '_ResponseMax', 1).enable(state).grid(
            row=3, column=3, sticky='nsew', padx=2, pady=2)
        subsection.pack(fill='x', padx=10, pady=10)
        section.pack(side='top', pady=10, padx=10, fill='both')

        Stimframe = self.AddTab('StimSettings', title='Stimulation')
        Stimframe['bg'] = bg

        # Stimulation Parameter
        section = tkinter.LabelFrame(Stimframe, text='Stimulus Scheduling', bg=bg)
        state = {True: 'normal', False: 'disabled'}[self.mode in ['st']]
        self.widgets.entry_isi_st = LabelledEntry(section, 'Min. interval for\nStimulus Test (sec)').connect(params,
                                                                                                             '_SecondsBetweenStimulusTests').enable(
            state).grid(row=1, column=1, sticky='e', padx=8, pady=8)
        state = {True: 'normal', False: 'disabled'}[self.mode in ['rc', 'ct', 'tt']]
        self.widgets.entry_isi = LabelledEntry(section, 'Min. interval for\nnormal usage(sec)').connect(params,
                                                                                                        '_SecondsBetweenTriggers').enable(
            state).grid(row=1, column=2, sticky='e', padx=8, pady=8)
        section.pack(side='top', pady=10, padx=10, fill='both')

        # Trial Numbers
        section = tkinter.LabelFrame(Stimframe, text='Trial Numbers', bg=bg)
        subsection = tkinter.Frame(section, bg=bg)

        # Switch that enables up or down counting
        state = {True: 'normal', False: 'disabled'}[self.mode in ['ct', 'tt']]
        self.widgets.switch_udTrialCounter = Switch(section, title='Count up/down:', offLabel='UP', onLabel='DOWN',values=['up', 'down'], initialValue='up').connect(params,'_UpDownTrialCount').enable(state).pack(side='left', padx=10, pady=10)

        state = {True: 'normal', False: 'disabled'}[self.mode in ['ct', 'tt']]
        self.widgets.entry_ctCount = LabelledEntry(subsection, 'Control Trials: ').connect(params,'_ctTrialsCount').enable(state).pack(side='left', padx=3)
        self.widgets.entry_ttCount = LabelledEntry(subsection, 'Training Trials: ').connect(params,'_ttTrialsCount').enable(state).pack(side='left', padx=3)

        subsection.pack(fill='x', padx=10, pady=10)
        section.pack(side='top', pady=10, padx=10, fill='both')

        # Stimulation
        section = tkinter.LabelFrame(Stimframe, text='Stimulation Current Step Control', bg=bg)
        subsection = tkinter.Frame(section, bg=bg)
        state = {True: 'normal', False: 'disabled'}[int(self.parent.operator.remote.GetParameter('EnableDS5ControlFilter'))==1 and hasattr(self.parent,'stimGUI')]
        self.widgets.entry_IncrementStart = LabelledEntry(subsection, 'Step Start: ').connect(params,'_IncrementStart').enable(True).pack(side='left', padx=3)
        self.widgets.entry_IncrementIncrement = LabelledEntry(subsection, 'Step Increment: ').connect(params,'_IncrementIncrement').enable(state).pack(side='left', padx=3)
        self.widgets.entry_CurrentLimit = LabelledEntry(subsection, 'Current Limit (mA): ').connect(params,'_CurrentLimit').enable(state).pack(side='bottom', padx=3)
        subsection.pack(fill='x', padx=10, pady=10)
        section.pack(side='top', pady=10, padx=10, fill='both')


        # Switch that enables Digitimer DS8 or DS5, disabled if parameters are disabled
        section = tkinter.LabelFrame(Stimframe, text='Digitimer Control panel', bg=bg)
        subsection = tkinter.Frame(section, bg=bg)
        DS5 = bool(self.parent.operator.remote.GetParameter('EnableDS5ControlFilter'))
        DS8 = bool(self.parent.operator.remote.GetParameter('EnableDS8ControlFilter'))
        state = {True: 'normal', False: 'disabled'}[DS5 or DS8]
        self.widgets.switch_DigitimerEnable = Switch(subsection, title='Digitimer Enable:', offLabel='ON', onLabel='OFF',
                                               values=['on', 'off'], initialValue='on').connect(params,'_DigitimerEnable').enable('normal').pack(side='left', padx=10, pady=10)

        self.widgets.switch_DigitimerSelect = Switch(subsection, title='DS5/DS8:', offLabel='DS5', onLabel='DS8',
                                                    values=['DS5', 'DS8'], initialValue='DS5').connect(params,'_DigitimerSelect').enable(state).pack(side='left', padx=10, pady=10)

        subsection.pack(fill='x', padx=10, pady=10)
        section.pack(side='top', pady=10, padx=10, fill='both')

        self.resizable(False, False)
        EMGframe.pack(side='top', padx=2, pady=2, fill='both', expand=1)
        Stimframe.pack(side='top', padx=2, pady=2, fill='both', expand=1)
        w1 = self.widgets.label_message = tkinter.Label(EMGframe, text='', bg=bg)
        w2 = self.widgets.label_message = tkinter.Label(Stimframe, text='', bg=bg)
        w1.pack(ipadx=10, ipady=10)
        w2.pack(ipadx=10, ipady=10)

    def mark( self, widgets, good=False, msg=None, color='#FF6666' ):
        if not isinstance( widgets, ( tuple, list ) ): widgets = [ widgets ]
        widgets = list( widgets )
        for i, widget in enumerate( widgets ): widgets[ i ] = getattr( widget, 'entry', widget )
        for widget in widgets: widget[ 'bg' ] = { True : '#FFFFFF', False : color }.get( bool( good ) )
        if len( widgets ): widgets[ -1 ].focus()
        if msg != None: self.error( msg )
        return good

    def ValueWarnings( self, widgetName, newString ):
        widget = self.nametowidget( widgetName )
        if len( newString.strip() ) == 0: newValue = None
        else:
            try: newValue = float( newString )
            except: return
        self.error( '', widget )
        if widget is self.widgets.entry_baselineresponse.entry:
            oldValue = self.parent.operator.params._BaselineResponse
            if oldValue != None and newValue != oldValue:
                msg = "The baseline marker was previously set at %g%s. Usually, it\nshould stay fixed for the whole of a patient's course of treatment." % ( oldValue, self.parent.operator.params._VoltageUnits )
                self.error( msg, widget, color=self.colors.warning_bg, highlight=self.colors.warning_highlight )
            else: self.mark( widget, good=True )
        if widget is self.widgets.entry_responsebar.entry:
            baseline = self.widgets.entry_baselineresponse.get().strip()
            try: baseline = float( baseline )
            except: baseline = None
            #baseline = self.parent.operator.params._BaselineResponse
            if baseline and newValue and float( '%g' % newValue ) != float( '%g' % ( 2 * baseline ) ):
                msg = 'Unless the patient is producing unusually large responses,\nthe response bar axes limit should be twice the baseline\nvalue (2 x %g = %g%s)' % ( baseline, baseline * 2, self.parent.operator.params._VoltageUnits )
                self.error( msg, widget, color=self.colors.warning_bg, highlight=self.colors.warning_highlight )
            else: self.mark( widget, good=True )
        return True

    def error( self, msg, *widgets, **kwargs ):
        color = kwargs.pop( 'color', self.colors.error_bg )
        highlight = kwargs.pop( 'highlight', self.colors.error_highlight )
        if len( kwargs ): raise TypeError( 'unexpected kwargs in error()' )
        if msg == None: msg = ''
        msgLabel = self.widgets.label_message
        if msg == '': bg = msgLabel.master[ 'bg' ]
        else: bg = color
        msgLabel.configure( text=msg, bg=bg, fg='#FFFFFF' )
        return self.mark( widgets, msg=='', color=highlight )

    def validate( self ):
        value = Bunch()
        entry = Bunch()
        for key, widget in self.widgets.items():
            if not key.startswith( 'entry_' ): continue
            self.mark( widget, good=True )

        for key, widget in self.widgets.items():
            if not key.startswith( 'entry_' ): continue
            key = key[ 6: ]
            x = widget.get().strip()
            if x == '':
                if key in 'baselineresponse bgmin1 bgmin2 bgmax1 bgmax2 rmin1 rmin2 rmax1 rmax2 ctCount ttCount'.split(): x = None
                else: return self.error( 'this cannot be blank', widget )
            else:
                try: x = float( x )
                except: return self.error( 'cannot interpret this as a number', widget )
                if x < 0.0: return self.error( 'this cannot be negative', widget )
                #'isi   backgroundbar refresh  responsebar baselineresponse    bgmin1 bgmax1 bgmin2 bgmax2   hold   rstart rend  rmin1 rmin2 rmax1 rmax2'
                if x == 0.0 and key in 'isi isi_st backgroundbar refresh  responsebar bgmax1 bgmax2  rmax1 rmax2 ctCount ttCount'.split(): return self.error( 'this cannot be zero', widget )
            value[ key ] = x
            entry[ key ] = widget

        if value.isi    < 2.0: return self.error( 'this should not be less than 2 seconds', entry.isi )
        if value.isi_st < 2.0: return self.error( 'this should not be less than 2 seconds', entry.isi_st )
        if value.bgmin1 != None and value.bgmax1 != None and value.bgmin1 >= value.bgmax1: return self.error( 'minimum must be less than maximum', entry.bgmin1, entry.bgmax1 )
        if value.bgmin2 != None and value.bgmax2 != None and value.bgmin2 >= value.bgmax2: return self.error( 'minimum must be less than maximum', entry.bgmin2, entry.bgmax2 )
        if value.rmin1  != None and value.rmax1  != None and value.rmin1  >= value.rmax1:  return self.error( 'minimum must be less than maximum', entry.rmin1,  entry.rmax1 )
        if value.rmin2  != None and value.rmax2  != None and value.rmin2  >= value.rmax2:  return self.error( 'minimum must be less than maximum', entry.rmin2,  entry.rmax2 )

        lookForwardMsec = float( self.parent.operator.params.LookForward.strip( 'ms' ) )
        if value.rend > lookForwardMsec: return self.error( 'this cannot be larger than %gms' % lookForwardMsec, entry.rend )
        msPerSegment = float( self.parent.operator.params.BackgroundSegmentDuration.strip( 'ms' ) )
        secondsPerSegment = msPerSegment / 1000.0
        def roundto( value, factor ): return float( '%g' % ( factor * round( value / float( factor ) ) ) )
        if value.refresh < 50: return self.error( 'this cannot be less than 50ms', entry.refresh )
        if value.rstart >= value.rend: return self.error( 'start must be earlier than end', entry.rstart, entry.rend )
        if value.rstart > value.rend - 1: return self.error( 'start must be earlier than end by at least 1ms', entry.rstart, entry.rend )

        if ((value.IncrementStart < 0) or (value.IncrementStart > 5)): return self.error( 'Current Steps must Start between 0 and 5mA', entry.IncrementStart)
        if ((value.IncrementIncrement < 0.125) or (value.IncrementIncrement > 2.5)): return self.error('Step Increments must be between 0.25 and 2.5mA', entry.IncrementIncrement)
        if ((value.IncrementStart % value.IncrementIncrement) != 0): return self.error( 'Current Step start value must be an integer multiple of the step increments',value.IncrementStart, entry.IncrementIncrement)
        if (value.CurrentLimit > 50): return self.error( 'Maximum Current must be set below 50mA', entry.CurrentLimit)

        if value.baselineresponse != None and value.baselineresponse != self.parent.operator.params._BaselineResponse:
            if float( str( value.responsebar ) ) != float( str( value.baselineresponse * 2 ) ):
                if getattr( self, 'response_scale_warning_delivered', None ) != ( value.baselineresponse, value.responsebar ):
                    self.response_scale_warning_delivered = ( value.baselineresponse, value.responsebar )
                    if self.parent.operator.params._BaselineResponse == None:
                        msg = 'Since you are setting the baseline level for the first\ntime, it is recommended that you set the response bar\naxes limit to twice the baseline, i.e. to %g. (Press\n"OK" again if you really want to proceed with %g.)' % ( value.baselineresponse * 2, value.responsebar )
                    else:
                        msg = 'Since you are changing the baseline level, it is\nrecommended that you set the response bar axes limit \nto twice the baseline, i.e. to %g. (Press "OK" again\nif you really want to proceed with %g.)' % ( value.baselineresponse * 2, value.responsebar )
                    return self.error( msg, self.widgets.entry_responsebar, color=self.colors.warning_bg, highlight=self.colors.warning_highlight )

        return True

    def apply( self ):
        changed = Bunch()
        for key, widget in self.widgets.items():
            if isinstance( widget, ConnectedWidget ):
                widget.push( changed )
        for k, v in sorted( changed.items() ):
            if v: self.parent.Log( 'Changed setting %s to %s' % ( k.strip( '_' ), repr( self.parent.operator.params[ k ] ) ) )
        if True in changed.values(): self.parent.operator.needSetConfig = True
        self.parent.SetBarLimits( 'vc', 'rc', 'ct', 'tt' )
        self.parent.SetTargets(   'vc', 'rc', 'ct', 'tt' )
        self.parent.SetTrialCount('ct','tt')
        self.parent.SetIncrement()
        self.parent.SetupDigitimer()
        self.parent.DrawFigures()

#class SubjectChooser( Dialog, TkMPL ):
#	def __init__( self, parent ): TkMPL.__init__( self ); Dialog.__init__( self, parent=parent, title='Start Session', icon=os.path.join( GUIDIR, 'epocs.ico' ) )
#	def apply( self ): self.successful = True
#	def buttonbox( self ): self.bind( "<Escape>", self.cancel )

class SubjectChooser( tkinter.Frame ):
    """
    A Tkinter.Frame subclass containing the GUI elements for specifying a subject ID and
    launching a session.

    The early implementation of this was as a separate Dialog subclass - the Dialog methods
    were retained when this transitioned to using the existing main EPOCS window and became
    just a type of Frame.
    """
    def __init__( self, parent, initialID='' ):

        tkinter.Frame.__init__( self, parent, bg=parent[ 'bg' ] )

        self.parent = parent
        self.initialID = initialID
        self.body( self )
        self.pack()
        self.wait_window()

    def ok( self ):
        self.successful = True
        self.destroy()

    def body( self, frame ):
        bg = frame[ 'bg' ]
        self.successful = False
        font = ( 'Helvetica', 15 )
        tkinter.Label( frame, text='Patient ID:', bg=bg, font=font  ).grid( row=1, column=1, sticky='e' )
        self.menuTitle = '(previous)'
        self.menuVar = v = tkinter.StringVar(); v.set( self.menuTitle ); v.trace( 'w', self.SelectFromMenu )
        self.menu = w = tkinter.OptionMenu( frame, v, self.menuTitle, *self.parent.operator.Subjects() ); w.configure( width=10, font=font ); w.grid( row=1, column=2, sticky='ew', pady=5 )
        self.subjectVar = v = tkinter.StringVar(); vcmd = ( self.register( self.ValidateKeyPress ), '%d', '%S', '%P' )
        self.entry = w = tkinter.Entry( frame, width=15, textvariable=v, validatecommand=vcmd, validate='key', font=font, bg='#FFFFFF' ); w.grid( row=1, column=3, sticky='ew', pady=5, padx=5 )
        self.newButton = w = tkinter.Button( frame, text='Start New Session', command=self.NewSession, state='disabled', font=font ); w.grid( row=1, column=4, sticky='ew', pady=5 )
        self.sessionInfo = w = tkinter.Label( frame, justify='center', bg=bg, font=font ); w.grid( row=2, column=1, columnspan=3, padx=20, sticky='ew' )
        self.continueButton = w = tkinter.Button( frame, text='Continue Session', command=self.ContinueSession, state='disabled', font=font ); w.grid( row=2, column=4, sticky='ew', pady=5 )
        self.subjectVar.set( self.initialID )
        self.ValidateKeyPress( '1', 'a', self.initialID )
        self.entry.focus()

    def ValidateKeyPress( self, editType, newKey, newString ):
        if str( editType ) == '1' and newKey.lower() not in 'abcdefghijklmnopqrstuvwxyz0123456789': return False
        previousSession = self.parent.operator.LastSessionStamp( newString )
        now = time.time()
        EnableWidget( self.newButton, len( newString ) > 0 )
        EnableWidget( self.continueButton, now < previousSession + 60 * 60 * 3 )
        if previousSession: msg = 'Last session started %s\n(%s)' % ( self.parent.operator.FriendlyDate( previousSession ), self.InformalTime( previousSession, now ) )
        elif len( newString ): msg = 'No previous sessions\n found for %s' % newString
        else: msg = ''
        self.sessionInfo[ 'text' ] = msg
        return True

    def SelectFromMenu( self, *args ):
        value = self.menuVar.get()
        if value not in [ '', self.menuTitle ]:
            self.menuVar.set( self.menuTitle )
            self.subjectVar.set( value )
            self.ValidateKeyPress( '1', 'a', value )

    def NewSession( self ):
        self.parent.operator.LoadSubjectSettings( self.subjectVar.get(), newSession=True )
        self.ok()

    def ContinueSession( self ):
        self.parent.operator.LoadSubjectSettings( self.subjectVar.get(), newSession=False )
        self.ok()

    def InformalTime(self, then, now ):
        seconds = float( now ) - float( then )
        def SetToNoon( t ): t = list( time.localtime( t ) ); t[ 3:6 ] = 12, 0, 0; return time.mktime( t ) # so fking tedious
        days = round( ( SetToNoon( now ) - SetToNoon( then ) ) / ( 60.0 * 60.0 * 24.0 ) )
        weeks = days / 7.0
        years = days / 365.25
        months = years * 12.0
        if   seconds < 50.0: return '%d seconds ago' % round( seconds )
        elif seconds < 90.0: return 'about a minute ago'
        elif seconds < 50*60.0: return '%d minutes ago' % round( seconds / 60.0 )
        elif seconds < 90*60.0: return 'about an hour ago'
        elif days == 0: return '%d hours ago' % round( seconds / 3600.0 )
        elif days == 1: return 'yesterday'
        elif days < 31: return '%d days ago' % days
        elif round(months) == 1: return 'about a month ago'
        elif months < 21: return  'about %d months ago' % round( months )
        elif round(years) == 1: return 'about a year ago'
        else: return  'about %d years ago' % round( years )

################

OFFLINE_ROOT = None
class OfflineAnalysis( object ):
    """
    This class impersonates the GUI class in a duck-typed sort of way when EPOCS is
    run in --offline mode.  It is like GUI() in that it creates both an Operator()
    instance (for managing settings) and an AnalysisWindow() instance, which will call
    methods of that Operator.
    """

    def __init__( self, data='ExampleData.pk', mode='tt' ):

        if isinstance( data, basestring ) and data.lower().endswith( '.pk' ):
            import pickle; self.data = Bunch( pickle.load( open( data, 'rb' ) ) )
        else: self.data = { mode : data }

        self.mode = mode
        self.operator = Operator()
        self.online_inifile  = os.path.join( GUIDIR, 'epocs.ini' );   self.operator.Set( **ReadDict( self.online_inifile  ) )
        self.offline_inifile = os.path.join( GUIDIR, 'offline.ini' ); self.operator.Set( **ReadDict( self.offline_inifile ) )
        self.SetSubject()
        self.initialdir = self.operator.DataRoot()
        #d = self.operator.DataDirectory()
        #while len( d ) and not os.path.exists( d ): d = os.path.realpath( os.path.join( d, '..' ) )
        #self.initialdir = d
        self.subject = None
        self.session = None

        self.modenames = MODENAMES
        self.axiscontrollers_emg1 = []

        self.logtext = ''
        self.logfile = sys.stdout

        global OFFLINE_ROOT
        if OFFLINE_ROOT == None:
            try: tkinter.ALLWINDOWS
            except: tkinter.ALLWINDOWS = []
            while len( tkinter.ALLWINDOWS ):
                try: tkinter.ALLWINDOWS.pop( 0 ).destroy()
                except: pass
            OFFLINE_ROOT = tksuperclass()
            OFFLINE_ROOT.option_add( '*Font', 'TkDefaultFont 13' )
            OFFLINE_ROOT.option_add( '*Label*Font', 'TkDefaultFont 13' )
            OFFLINE_ROOT.withdraw()
            tkinter.ALLWINDOWS.append( OFFLINE_ROOT )
        self.tkparent = OFFLINE_ROOT
        # There now follows some furious duck-typing to deal with the fact that the AnalysisWindow
        # refers to its "parent" for two distinct types of information: Tk GUI info (used during
        # tkinter-specific __init__ and methods of the Dialog base-class) and info about the analysis
        # to be carried out.   The Tk GUI parent is a jealous god: there can be only one (hence the
        # use of a single global OFFLINE_ROOT above). But we want to allow for the possibility of
        # multiple analysis cases in memory at the same time (i.e. multiple instances of the
        # OfflineAnalysis class, each spawning a window).  A better but more invasive solution would
        # have been to re-write the AnalysisWindow class so that it explicitly acknowledges the two
        # different types of "parent" and does not confuse them.

        # These are things that are required because they seem to be used in tkinter code:
        for field in 'tk _w children master iconname title'.split(): setattr( self, field, getattr( self.tkparent, field ) )
        # And these are things that are knowingly used in the AnalysisWindow code:
        for field in 'after after_cancel'.split(): setattr( self, field, getattr( self.tkparent, field ) )
        # see also methods below

        self.tkparent.clipboard_clear()

    def __repr__( self ):
        s = object.__repr__( self ) + ':'
        for k, v in sorted( self.operator.params.items() ): s += '\n%50s = %s' % ( k, repr( v ) )
        return s

    def SetSubject( self, subjectName=None, sessionStamp=None ):
        fmt = self.operator.dateFormat
        def DecodeSessionStamp( subdir, parent=None ):
            if subdir in [ 0, None, '' ]: return 0
            if parent != None and not os.path.isdir( os.path.join( parent, subdir ) ): return 0
            n = len( time.strftime( fmt, time.localtime( 0 ) ) )
            try: return time.mktime( time.strptime( os.path.split( subdir )[ -1 ][ -n : ], fmt ) )
            except: return 0
        if subjectName == None: subjectName = self.operator.params.SubjectName
        if subjectName  not in [ None, '' ]:
            self.operator.Set( SubjectName=subjectName )
        if sessionStamp not in [ None ]:
            self.operator.Set( SessionStamp=sessionStamp )
            if not DecodeSessionStamp( self.operator.params.SessionStamp ):
                self.operator.Set( SessionStamp=self.operator.LastSessionStamp() )
            if not DecodeSessionStamp( self.operator.params.SessionStamp ):
                d = os.path.realpath( os.path.join( self.operator.DataDirectory(), '..' ) )
                last = max( [ 0 ] + [ DecodeSessionStamp( x, d ) for x in os.listdir( d ) ] )
                self.operator.Set( SessionStamp=time.strftime( fmt, time.localtime( last ) ) )
        if subjectName  not in [ None, '' ]:
            self.operator.Set( **self.operator.ReadSubjectSettings( suffix='' ) )
            self.operator.Set( **self.operator.ReadSubjectSettings( suffix='-Offline' ) )


    def CloseWindow( self, window=None ):
        if self.subject and self.session:
            if hasattr( window, 'overlay' ) and window.channel < 2:
                self.operator.params._TraceLimitVolts[ window.channel ] = max( window.overlay.yController.get() )
            try: self.operator.WriteSubjectSettings( subjectName=self.subject, suffix='-Offline' )
            except: self.Log( 'failed to save offline analysis settings' )
        if window != None: window.cancel()

    def Go( self ):
        a = AnalysisWindow( parent=self, mode=self.mode, modal=False, online=False, geometry='+0+0' )
        a.title( 'EPOCS Offline Analysis: ' + self.GetDescription() )
        a.protocol( "WM_DELETE_WINDOW", Curry( self.CloseWindow, window=a ) )
        if DEVEL: self.child = a # only do this during DEVEL because it creates a mutual reference loop and hence a memory leak
        return a

    def ListDatFiles( self ):
        return sorted( glob.glob( os.path.join( self.operator.DataDirectory(), '*.dat' ) ) )

    def ReadDatFile( self, filename, **kwargs ):
        from BCPy2000.BCI2000Tools.Chain import bci2000root, bci2000chain  # also imports BCI2000Tools.Parameters as a central component and SigTools for a few things

        if bci2000root() == None: bci2000root( os.path.join( BCI2000LAUNCHDIR, '..' ) )
        filename = TryFilePath( filename, os.path.join( self.operator.DataDirectory(), filename ) )
        self.Log( 'reading ' + filename )
        s = bci2000chain( filename, 'IIRBandpass', **kwargs )
        try: trigIndex = s.Parms.ChannelNames.Value.index( s.Parms.TriggerChannel.Value )
        except ValueError: trigIndex = s.Parms.TriggerChannel.NumericValue - 1
        p = s.ImportantParameters = Bunch(
            LookBack         = s.Parms.LookBack.ScaledValue / 1000.0,
            LookForward      = s.Parms.LookForward.ScaledValue / 1000.0,
            SamplingRate     = s.Parms.SamplingRate.ScaledValue,
            SampleBlockSize  = s.Parms.SampleBlockSize.NumericValue,
            SubjectName      = s.Parms.SubjectName.Value,
            SessionStamp     = s.Parms.SessionStamp.Value,
            SubjectRun       = 'R%02d' % s.Parms.SubjectRun.NumericValue,
            ApplicationMode  = s.Parms.ApplicationMode.Value.lower(),
            ResponseInterval = tuple( s.Parms.ResponseDefinition.ScaledValue[ 0, [ 1, 2 ] ] ),
        )

        try: import BCPy2000.SigTools.NumTools as NumTools # TODO: it would be nice to use the TrapFilter as a command-line filter as well, instead of the NumTools code (edges, epochs, refrac and diffx are needed). But for now BCI2000 framework bugs prevent this (or at least make it impossibly difficult to debug the problems I have observed if they really arise from TrapFilter itself)
        except ImportError: import NumTools # py2exe fallback: the file for BCPy2000.SigTools.NumTools will be included by hand but the rest of BCPy2000.SigTools will be excluded
        s.Epochs = s.__class__()
        # In FullMonty-based operation using epocs.py, scipy will be available, so BCI2000Tools.Chain will successfully import SigTools,
        # so the container class will be a SigTools.sstruct and the above command will be unnecessary.   By contrast, in the py2exe-made
        # version, scipy and SigTools will be excluded. Later versions of BCI2000Tools (bci2000.org r4734 and up) are sensitive to this
        # possibility, and fall back on the lighter-weight code in BCI2000Tools.LoadStream2Mat, where our Bunch() class is replicated -
        # in this case, the line above is necessary to initialize the empty substruct container.
        edgeIndices = NumTools.edges( s.Signal[ :, trigIndex ] >= s.Parms.TriggerThreshold.ScaledValue )
        s.Epochs.Data, s.Epochs.Time, s.Epochs.Indices = NumTools.epochs( s.Signal / 1e6, edgeIndices, length=p.LookForward + p.LookBack, offset=-p.LookBack, refractory=0.5, fs=p.SamplingRate, axis=0, return_array=True )
        self.Log( 'used %d of %d triggers' % ( len( s.Epochs.Indices ), len( edgeIndices ) ) )
        if len( s.Epochs.Data ): s.Epochs.Data = list( s.Epochs.Data.transpose( 0, 2, 1 ) ) # AnalysisWindow and its subplots will expect trials by channels by time
        return s

    def OpenFiles( self, filenames=None, **kwargs ):
        import numpy
        if filenames == None:
            import tkFileDialog
            filenames = tkFileDialog.askopenfilenames( initialdir=self.initialdir, title="Select one or more data files", filetypes=[ ( "BCI2000 .dat file" , ".dat" ) , ( "All files" , ".*" ) ] )
            if isinstance( filenames, basestring ): # you suck, tkFileDialog.askopenfilenames, for changing your output format from an easy-to-use tuple in Python 2.5 to an impossibly awkward single string in later versions
                joined = filenames; filenames = []
                while len( joined ):
                    m = re.match( r'\{(.+?)\}', joined )
                    if m: filenames.append( m.group().strip( '{}' ) ); joined = joined[ m.end() : ].strip(); continue
                    m = re.match( r'(\S+?)\s+', joined + ' ' )
                    if m: filenames.append( m.group().strip() ); joined = joined[ m.end() : ].strip(); continue
                    joined = joined.strip()
            # look how many lines of annoying difficult-to-debug crap you made me write.
            filenames = sorted( filenames )
        if not filenames: return
        objs = [ self.ReadDatFile( filename, **kwargs ) for filename in filenames ]

        if objs[0].ImportantParameters['ApplicationMode'] == 'vc':
            objs = [obj for obj in objs]
        else:
            objs = [ obj for obj in objs if len( obj.Epochs.Data ) ] # TODO: seems to exclude VC files
        if (len( objs ) == 0):
            print '\nFound no trials.'
            import tkMessageBox; tkMessageBox.showerror( "EPOCS Offline Analysis", '\n   '.join( [ "No trials found after scanning the following:" ] + filenames ) )
            return

        self.initialdir = os.path.split( filenames[ 0 ] )[ 0 ]
        first = objs[ 0 ].ImportantParameters
        unique = Bunch( [ ( field, sorted( set( [ obj.ImportantParameters[ field ] for obj in objs ] ) ) ) for field in first ] )
        errs = []
        for field in 'LookBack LookForward SamplingRate SampleBlockSize'.split():
            vals = unique[ field ]
            if len( vals ) > 1: errs.append( "%s setting differs between runs (values %s)" % ( field, repr( vals ) ) )
        if len( errs ): raise ValueError( '\n   '.join( [ "runs are incompatible unless you explicitly override the following:" ] + errs ) )

        if len( unique.ApplicationMode ) == 1:
            self.mode = unique.ApplicationMode[ 0 ].lower()
            if self.mode not in [ 'vc' ]: self.mode = 'offline' # TODO: and yet VC plotting mode seems to crash
        else:
            self.Log( 'WARNING: data are from mixed modes %s' % repr( unique.ApplicationMode ) )
            self.mode = 'mixed'

        if len( unique.SubjectName ) == 1:
            self.subject = unique.SubjectName[ 0 ]
            self.SetSubject( self.subject )
        else:
            self.Log( 'WARNING: data are mixed across subjects %s' % repr( unique.SubjectName ) )
            self.subject = None

        if len( unique.SessionStamp ) == 1:
            self.session = unique.SessionStamp[ 0 ]
            self.operator.Set( SessionStamp=self.session )
        else:
            self.Log( 'WARNING: data are mixed across sessions %s' % repr( unique.SessionStamp ) )
            self.session = None

        if len( unique.ResponseInterval ) > 1:
            self.Log( 'WARNING: data have different response intervals in ResponseDefinition parameter: %s' % repr( unique.ResponseInterval ) )
        self.operator.Set( _ResponseStartMsec=[ objs[ -1 ].ImportantParameters.ResponseInterval[ 0 ] ] * 2 )
        self.operator.Set( _ResponseEndMsec = [ objs[ -1 ].ImportantParameters.ResponseInterval[ 1 ] ] * 2 )

        self.runs = unique.SubjectRun
        self.fs = float( unique.SamplingRate[ 0 ] )
        self.sbs = float( unique.SampleBlockSize[ 0 ] )
        self.lookback = float( unique.LookBack[ 0 ] )
        if self.mode not in 'vc': data = reduce( list.__add__, [ obj.Epochs.Data for obj in objs ] )
        else:
            data = objs[0].States.BackgroundFeedbackValue / 1e6
            data = data.tolist()

        self.data = { self.mode : data }
        self.GetCurrents(objs)
        window = self.Go()
        return window

    def GetCurrents(self,objs,mode=None):
        import numpy
        #If using the Digitimer stimulator, we have the currents used to pass to AnalysisWindow()
        try:
            locs = numpy.where(numpy.diff(objs[0].States.TrialsCompleted) > 0)
            Currents = objs[0].States.CurrentAmplitude[locs]
            self.Currents = Currents.tolist()
        except:
            self.Currents = []

    # more duck-typing
    def GetDescription( self, mode=None ):
        subject = self.subject
        if subject == None: subject = 'multiple subjects'
        session = self.session
        if session == None: session = 'multiple sessions'
        return '%s - %s - %s' % ( subject, session, ','.join( self.runs ) )

    def Log( self, text, datestamp=True ):
        if datestamp: stamp = self.operator.FriendlyDate( time.time() ) + '       '
        else: stamp = ''
        text = stamp + text + '\n'
        if len( self.logtext ) and not self.logtext.endswith( '\n' ): self.logtext += '\n'
        self.logtext += text
        if self.logfile: self.logfile.write( text ) # TODO
        self.tkparent.clipboard_append( text )
        self.tkparent.update()
    # vestigial duck traits (actually these should never even be called, if the up-conditioning and down-conditioning buttons are not made visible)
    def SetBarLimits( self, *pargs, **kwargs ): pass
    def SetTarget( self, *pargs, **kwargs ): pass

################




if __name__ == '__main__':

    args = getattr( sys, 'argv', [] )[ 1: ]

    try: import EpocsCommandLineArguments  # if present, this might say something like args = [ "--offline" ]
    except ImportError: pass  # if absent, no biggy
    else: args += EpocsCommandLineArguments.args  # this is a way of smuggling hard-coded command-line arguments into a py2exe binary

    import getopt
    opts, args = getopt.getopt( args, '', [ 'log=', 'devel', 'debug', 'offline', 'custom=' ] )
    opts = dict( opts )
    log = opts.get( '--log', None )
    os.environ[ 'EPOCSTIMESTAMP' ] = time.strftime( '%Y%m%d-%H%M%S' )
    if log:
        log = log.replace( '###', os.environ[ 'EPOCSTIMESTAMP' ] )
        logDir = os.path.split( log )[ 0 ]
        if not os.path.isdir( logDir ): os.mkdir( logDir )
        sys.stdout = sys.stderr = open( log, 'wt', 0 )
    if '--devel' in opts: DEVEL = True  # use FilePlayback as signal source, and load example data at launch for easy test of analysis window
    if '--debug' in opts: DEBUG = True  # print debug messages to the system log, and possibly perform other temporary "weird" debugging operations (independent of whether we're in FilePlayback mode)
    CUSTOM = opts.get( '--custom', '' )

    try: tkinter.ALLWINDOWS
    except: tkinter.ALLWINDOWS = []
    while len( tkinter.ALLWINDOWS ):
        try: tkinter.ALLWINDOWS.pop( 0 ).destroy()
        except: pass

    if DEBUG:
        flush( 'Python ' + sys.version )
        flush( 'matplotlib ' + str( matplotlib.__version__ ) )
        flush( tkinter.__name__ + ' ' + str( tkinter.__version__ ) )
        if 'ttk' in sys.modules: flush( 'ttk ' + str( ttk.__version__ ) )
        else: flush( 'no ttk (must be using Tix)' )

    #self = OfflineAnalysis()
    #window = self.OpenFiles()
    #if window: window.wait_window()

    if '--offline' in opts:
        self = OfflineAnalysis()
        window = self.OpenFiles()
        if window: window.wait_window()
    else:
        self = GUI()
        #self.operator.remote.WindowVisible = 1
        if self.ready: self.Loop()

    if log:
        # remove the python log if it is empty
        if sys.stdout.tell() == 0: sys.stdout.close(); os.remove( log )
        # remove the operator log if it's there and if it doesn't contain the words "warning", "error" or "exception"
        logDir, logName = os.path.split( log )
        operatorLog = os.path.join( logDir, os.environ[ 'EPOCSTIMESTAMP' ] + '-operator.txt' )
        if os.path.isfile( operatorLog ):
            content = open( operatorLog, 'rt' ).read().lower()
            #if 'warning' not in content and 'error' not in content and 'exception' not in content: os.remove( operatorLog )

