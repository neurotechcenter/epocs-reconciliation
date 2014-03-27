"""
TODO	
	offline analysis
		use BCPy2000 tools to read .dat file: either BCI2000.FileReader, or (preferably) fix BCI2000 filtertools and use them
		allow access to multi-file offline analysis via "advanced" mode (possibly hidden?) in EPOCS GUI
	
	"are you sure you want to quit?"
	
	make separate settings entry to govern maximum random extra hold duration?  (if so: remember to enforce its rounding to whole number of segments)
	
	NIDAQmxADC: acquisition of floating-point raw data instead of integers
	
	NB: assuming background is in range, time between triggers is actually MinTimeBetweenTriggers + 1 sample block
"""

import os, sys, time, math, re, threading
import mmap, struct
import inspect
import Tkinter as tkinter
import matplotlib, matplotlib.pyplot

tksuperclass = tkinter.Tk
try: import ttk
except ImportError: import Tix; tksuperclass = Tix.Tk  # ...because Python 2.5 does not have ttk
	
import ctypes
try: ctypes.windll.nicaiu
except: DEVEL = True
else:   DEVEL = False

DEBUG = False

GUIDIR = os.path.dirname( os.path.realpath( inspect.getfile( inspect.currentframe() ) ) )
BCI2000LAUNCHDIR = os.path.abspath( os.path.join( GUIDIR, '../prog' ) )
if not os.path.isfile( os.path.join( BCI2000LAUNCHDIR, 'BCI2000Remote.py' ) ): raise ImportError( 'could not find the prog directory containing BCI2000Remote.py' )
if BCI2000LAUNCHDIR not in sys.path: sys.path.append( BCI2000LAUNCHDIR )
import BCI2000Remote

def flush( s ): sys.stdout.write( str( s ) + '\n' ); sys.stdout.flush()

class Bunch( dict ):
	def __init__( self, d=(), **kwargs ): dict.__init__( self, d ); dict.update( self, kwargs )
	def update( self, d=(), **kwargs ): dict.update( self, d ); dict.update( self, kwargs ); return self
	def __getattr__( self, key ):
		if key in self.__dict__: return self.__dict__[ key ]
		elif key in self: return self[ key ]
		else: raise AttributeError( "'%s' object has no attribute or item '%s'" % ( self.__class__.__name__, key ) )
	def __setattr__( self, key, value ):
		if key in self.__dict__: self.__dict__[ key ] = value
		else: self[ key ] = value
	def _getAttributeNames( self ): return self.keys()
	
def Curry( func, *creation_time_pargs, **creation_time_kwargs ):
	def curried( *call_time_pargs, **call_time_kwargs ):
		pargs = creation_time_pargs + call_time_pargs
		kwargs = dict( creation_time_kwargs )
		kwargs.update( call_time_kwargs )
		return func( *pargs, **kwargs )
	curried.__doc__ = 'curried function %s(%s)' % ( func.__name__, ', '.join( [ repr( v ) for v in creation_time_pargs ] + [ '%s=%s' % ( str(k), repr(v) ) for k, v in creation_time_kwargs.items() ] ) )
	if func.__doc__: curried.__doc__ += '\n' + func.__doc__
	return curried

def GenericCallback( *pargs, **kwargs ):
	print pargs
	print kwargs
	return 'yeah!'

def ResolveDirectory( d, startDir=None ):
	oldDir = os.getcwd()
	if startDir == None: startDir = oldDir
	os.chdir( startDir )
	result = os.path.abspath( d )
	os.chdir( oldDir )
	return result

def MakeWayFor( filepath ):
	# we were relying on setconfig to do this for us, but a bug in BCI2000 means we cannot setconfig twice in a row without performing a run in between (if we do, the parameter values are not all updated correctly from the first to the second time)
	parent = os.path.split( filepath )[ 0 ]
	if len( parent ) and not os.path.isdir( parent ): os.makedirs( parent )
	return filepath

def WriteDict( d, filename, *fields ):
	if len( fields ): d = dict( ( k, v ) for k, v in d.items() if k in fields )
	file = open( MakeWayFor( filename ), 'wt' )
	file.write( '{\n' )
	for k, v in sorted( d.items() ): file.write( '\t%s : %s,\n' % ( repr( k ), repr( v ) ) )
	file.write( '}\n' )
	file.close()

class Operator( object ):
	def __init__( self ):
		
		self.dateFormat = '%Y-%m-%d-%H-%M'
		self.sessionStamp = None
		self.needSetConfig = True
		self.started = False
		
		self.mmfilename = 'epocs.mmap'
		self.mmfile = None
		self.mm = None
		
		dataDir = '../../data'
		
		self.params = Bunch(
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
			
			_EMGChannelNames =       [ 'EMG1', 'EMG2', ],  # "parameter" names beginning with '_' are not real BCI2000 parameters
			_BackgroundMin =         [     5,      0,  ],  # and will not be sent to BCI2000 automatically. Rather, the appropriate
			_BackgroundMax =         [    18,     15,  ],  # matrix parameters will be constructed from them in SendConditioningParameters()
			
			_ResponseStartMsec =     [    38,     38,  ],
			_ResponseEndMsec =       [    45,     45,  ],
			
			_ComparisonStartMsec =   [    19,     19,  ],
			_ComparisonEndMsec =     [    23,     23,  ],
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
			
			_VoltageUnits = 'mV',
			
			_SecondsBetweenTriggers = 5,
			_SecondsBetweenStimulusTests = 3,
			_BarUpdatePeriodMsec = 200,
			_BackgroundHoldSec = 2,       # should be an integer multiple of BackgroundSegmentDuration
			_BackgroundHoldExtraSec = 0,  # should be an integer multiple of BackgroundSegmentDuration
				
		)
		
		self.remote = BCI2000Remote.BCI2000Remote()
		self.remote.Connect()
	
	def Launch( self ):
		if DEVEL: self.bci2000( 'execute script ../batch/run-nidaqmx.bat slave devel' )
		else:     self.bci2000( 'execute script ../batch/run-nidaqmx.bat slave' )
	
	def DataRoot( self ):
		return ResolveDirectory( self.params.DataDirectory, BCI2000LAUNCHDIR )
	
	def SettingsFile( self, subjectName=None ):
		if subjectName == None: subjectName = self.params.SubjectName
		if not subjectName: return ''
		return os.path.join( self.DataRoot(), subjectName, subjectName + '-LastSettings.txt' )

	def Subjects( self ):
		dataRoot = self.DataRoot()
		if not os.path.isdir( dataRoot ): return []
		return [ x for x in os.listdir( dataRoot ) if os.path.isfile( self.SettingsFile( x ) ) ]
			
	def ReadSettings( self, subjectName=None ):
		filename = self.SettingsFile( subjectName )
		if not os.path.isfile( filename ): return { 'SubjectName': subjectName }
		return eval( open( filename, 'rt' ).read() )
	
	def LoadSettings( self, subjectName=None, newSession=False ):
		self.Set( **self.ReadSettings( subjectName ) )
		if newSession: self.Set( SessionStamp=time.time() )
		
	def WriteSettings( self ):
		d = dict( ( k, v ) for k, v in self.params.items() if k in 'SubjectName SessionStamp'.split() or k.startswith( '_' ) )
		WriteDict( d, self.SettingsFile() )

	def LastSessionStamp( self, subjectName ):
		record = self.ReadSettings( subjectName )
		try: return time.mktime( time.strptime( record[ 'SessionStamp' ], self.dateFormat ) )
		except: return 0

	def GetVolts( self, value ):
		return GetVolts( value, self.params._VoltageUnits )		
	
	def DataFile( self, runNumber=None, autoIncrement=False ):
		if runNumber == None: runNumber = self.params.SubjectRun
		runNumber = int( runNumber )
		runString = '%02d' % runNumber
		if runNumber == 0:
			runNumber = 1
			autoIncrement = True
		if autoIncrement: runString = '*'
		s = os.path.split( self.params.DataFile )[ 1 ]
		for k, v in self.params.items():
			if k is 'SubjectRun': v = runString
			match = '${%s}' % k
			if match in s: s = s.replace( match, v )
		if autoIncrement:
			d = self.DataDirectory()
			while True:
				candidate = s.replace( '*', '%02d' % runNumber )
				if not os.path.isfile( d + '/' + candidate ): break
				runNumber += 1
			s = candidate
		return s
	
	def FriendlyDate( self, stamp=None ):
		if stamp == None: stamp = self.sessionStamp
		return time.strftime( '%Y-%m-%d  %H:%M', time.localtime( stamp ) )
	
	def LastRunNumber( self, mode='' ):
		d = self.DataDirectory()
		if not os.path.isdir( d ): return 0
		runs = [ self.RunNumber( x ) for x in os.listdir( d ) if x.lower().endswith( ( mode + '.' + self.params.FileFormat ).lower() ) ]
		if len( runs ) == 0: return 0
		return max( runs )
		
	def NextRunNumber( self ):
		return self.LastRunNumber() + 1  # let the numbering be global - look for the last run number in *any* mode
		
	def RunNumber( self, datfilename ):
		parentdir, datfile = os.path.split( datfilename )
		stem, ext = os.path.splitext( datfilename )
		stem = '-' + '-'.join( stem.split( '-' )[ 1: ] ) + '-'
		m = re.match( '.*-R([0-9]+)-.*', stem )
		if m == None: return None
		return int( m.groups()[ 0 ] )
		
	def DataDirectory( self ):
		s = '${DataDirectory}/' + self.params.DataFile
		for k, v in self.params.items():
			match = '${%s}' % k
			if match in s: s = s.replace( match, v )
		d = os.path.split( s )[ 0 ]
		return ResolveDirectory( d, BCI2000LAUNCHDIR )
	
	def LogFile( self, autoCreate=False ):
		logfile = os.path.join( self.DataDirectory(), '%s-%s-log.txt' % ( self.params.SubjectName, self.params.SessionStamp ) )
		if autoCreate and not os.path.isfile( logfile ):
			f = open( MakeWayFor( logfile ), 'at' )
			f.write( 'Patient Code: %s\nSession Code: %s\n\n' % ( self.params.SubjectName, self.params.SessionStamp ) )
			f.close()
		return logfile
		
	def Set( self, **kwargs ):
		container = self.params
		for key, value in kwargs.items():
			#flush( repr( key ) + ' : ' + repr( value ) )
			old = getattr( container, key, None )
			if key == 'SubjectName':
				cleaned = ''.join( c for c in value if c.lower() in 'abcdefghijklmnopqrstuvwxyz0123456789' )
				if cleaned == '': raise ValueError( 'invalid subject name "%s"' % value )
				else: value = cleaned
			if key == 'SessionStamp':
				if isinstance( value, float ): value = time.strftime( self.dateFormat, time.localtime( value ) )
			if value != old:
				if self.started: raise RuntimeError( "must call Stop() method first" )
				self.needSetConfig = True
			setattr( container, key, value )
			if key == 'SessionStamp':
				self.sessionStamp = time.mktime( time.strptime( value, self.dateFormat ) )
		
	def bci2000( self, cmd ):
		#flush( cmd )
		#os.system( os.path.join( '..', '..', '..', 'prog', 'BCI2000Shell' ) + ' -c ' + cmd )
		return self.remote.Execute( cmd )
		
	def SendParameter( self, key, value=None ):
		if value == None: value = self.params[ key ]
		value = str( value )
		for ch in '% ${}': value = value.replace( ch, '%%%02x' % ord(ch) )
		if value == '': value = '%'
		self.bci2000( 'set parameter %s %s' % ( key, value ) )
	
	def SendConditioningParameters( self ):
		
		channelNames = [ x.replace( ' ', '%20' ) for x in self.params._EMGChannelNames ] # TODO: for now, we'll have to assume that these names are correctly configured in the parameter file
		units = self.params._VoltageUnits
		
		def stringify( listOfNumbers ):
			out = []
			for x in listOfNumbers:
				if x == None: out.append( '%' )
				else: out.append( '%g%s' % ( x, units ) )
			return out
		
		minV, maxV = stringify( self.params._BackgroundMin ), stringify( self.params._BackgroundMax )
		if self.params.ApplicationMode.lower() in [ 'vc' ]:
			minV, maxV = [ '%' for x in minV ], [ '%' for x in maxV ]
		
		cols =   'Input%20Channel   Subtract%20Mean?   Norm    Min%20Amplitude     Max%20Amplitude    Feedback%20Weight'
		rows = [ '      %s                 yes           1          %s                  %s                   %g        '  %
		         (     name,                                      minV[ i ],         maxV[ i ],            i == 0,     ) for i, name in enumerate( channelNames ) ]
		self.bci2000( 'set parameter Background matrix BackgroundChannels= ' + str( len( rows ) ) + ' { ' + cols + ' } ' + ' '.join( rows ) )
		
		start, end = self.params._ResponseStartMsec, self.params._ResponseEndMsec
		cols =   'Input%20Channel   Start        End   Subtract%20Mean?   Norm    Weight   Response%20Name'
		rows = [ '    %s            %gms        %gms         no             1       1.0          %s       ' %
		         (    name,      start[ i ],  end[ i ],                                      name,        ) for i, name in enumerate( channelNames ) ]
		self.bci2000( 'set parameter Responses  matrix ResponseDefinition= ' + str( len( rows ) ) + ' { ' + cols + ' } ' + ' '.join( rows ) )

		minV, maxV = stringify( self.params._ResponseMin ), stringify( self.params._ResponseMax )
		cols =   'Response%20Name     Min%20Amplitude      Max%20Amplitude    Feedback%20Weight'
		rows = [ '     %s                  %s                  %s                    %g        ' %
		         (    name,              minV[ i ],         maxV[ i ],             i == 0      ) for i, name in enumerate( channelNames ) ]
		self.bci2000( 'set parameter Responses  matrix ResponseAssessment= ' + str( len( rows ) ) + ' { ' + cols + ' } ' + ' '.join( rows ) )

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
		
		bgLimit, rLimit, rBaseline = stringify( [ self.GetBackgroundBarLimit( self.params.ApplicationMode ), self.params._ResponseBarLimit, self.params._BaselineResponse ] )
		
		self.SendParameter( 'BackgroundScaleLimit',  bgLimit )
		self.SendParameter( 'ResponseScaleLimit',    rLimit )
		self.SendParameter( 'BaselineResponseLevel', rBaseline )

	def GetBackgroundBarLimit( self, mode ):
		mode = mode.lower()
		lower, upper = self.params._BackgroundMin[ 0 ], self.params._BackgroundMax[ 0 ]
		if mode in [ 'vc' ]: return self.params._VCBackgroundBarLimit
		elif lower == None and upper == None: return self.params._VCBackgroundBarLimit
		elif lower == None and upper != None: return upper * 2.0
		elif lower != None and upper == None: return lower * 2.0
		else: return lower + upper
	
	def SetConfig( self, work_around_bci2000_bug=False ):
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
			self.bci2000( 'setconfig' )
			self.needSetConfig = False
		self.WriteSettings()
		
		
	def Stop( self ):
		if self.mm:
			self.mmlock.acquire()
			self.mm = None
			self.mmfile.close()
			self.mmlock.release()
		self.bci2000( 'set state Running 0' )
		self.started = False
		
	def Start( self, mode=None ):
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
		if not self.mm: return 0
		fmt = '@L'
		return struct.unpack( fmt, self.mm[ :struct.calcsize( fmt ) ])[ 0 ]

def FixAspectRatio( widget, aspect_ratio=None, relx=0.5, rely=0.5, anchor='center' ):
	"Adapted from Bryan Oakley's answer to http://stackoverflow.com/questions/16523128 "
	if aspect_ratio == None: aspect_ratio = float( widget[ 'height' ] ) / float( widget[ 'width' ] )
	def EnforceAspectRatio( event ):
		desired_width = event.width
		desired_height = int( 0.5 + event.width * float( aspect_ratio ) )
		if desired_height > event.height:
			desired_height = event.height
			desired_width = int( 0.5 + event.height / float( aspect_ratio ) )
		widget.place( relx=relx, rely=rely, anchor=anchor, width=desired_width, height=desired_height )
	widget.master.bind( "<Configure>", EnforceAspectRatio )
	return widget
	
def EnableWidget( widget, enabled=True ):
	if isinstance( widget, ( tuple, list ) ):
		for w in widget: EnableWidget( w, enabled )
		return
	if enabled: widget.configure( state='normal' )
	else: widget.configure( state='disabled' )

def FormatWithUnits( value, context=None, units='', fmt='%+g', stripZeroSign=True, appendUnits=True ):
	if context == None: context = [ value ]
	extreme = max( abs( x ) for x in context )
	if units == None: units = ''
	if units == '':           factor = 1e0; prefix = ''
	elif extreme <=  2000e-9: factor = 1e9; prefix = 'n'
	elif extreme <=  2000e-6: factor = 1e6; prefix = u'\u00b5'   # up to +/- 2 milliVolts, use microVolts
	elif extreme <=  2000e-3: factor = 1e3; prefix = 'm'         # up to +/- 2 Volts, use milliVolts
	else:                     factor = 1e0; prefix = ''
	s = fmt % ( value * factor )
	if stripZeroSign and value == 0.0 and s.startswith( ( '-', '+' ) ): s = s[ 1: ]
	if appendUnits: s += prefix + units
	return s

def TimeBase( values, fs, lookback ):
	return [ sample / fs - lookback for sample, value in enumerate( values ) ]

def GetVolts( value, units ):
	if isinstance( value, ( tuple, list ) ): return value.__class__( GetVolts( x, units ) for x in value )
	if value == None: return None
	factors = { '' : 1e0, 'v' : 1e0, 'mv' : 1e-3, 'muv' : 1e-6, 'uv' : 1e-6 }
	return value * factors[ units.lower() ]

class Switch( tkinter.Frame ):
	def __init__( self, parent, title='', offLabel='off', onLabel='on', initialValue=0, command=None, values=( False, True ), bg=None, **kwargs ):
		if bg == None: bg = parent[ 'bg' ]
		tkinter.Frame.__init__( self, parent, bg=bg )
		self.title = tkinter.Label( self, text=title, justify='right', bg=bg )
		self.title.pack( side='left', fill='y', expand=True )
		self.offLabel = tkinter.Label( self, text=offLabel, justify='right', bg=bg )
		self.offLabel.pack( side='left', fill='y', expand=True )
		self.scale = tkinter.Scale( self, showvalue=0, orient='horizontal', from_=0, to=1, length=50, sliderlength=20, command=self.switched )
		self.scale.configure( troughcolor=bg, borderwidth=1 )
		self.scale.configure( **kwargs )
		self.scale.pack( side='left' )
		self.onLabel = tkinter.Label( self, text=onLabel, justify='left', bg=bg )
		self.onLabel.pack( side='right', fill='y', expand=True )
		self.command = command
		self.values = values
	def get( self ): return self.scale.get()
	def set( self, value ): return self.scale.set( value )
	def switched( self, arg=None ):
		colors = '#000000', '#888888'
		state = self.scale.get()
		if state: colors = colors[ ::-1 ]
		self.offLabel[ 'fg' ], self.onLabel[ 'fg' ] = colors
		if self.command: self.command( self.values[ state ] )
	
class AxisController( object ):
	def __init__( self, axes, axisname='x', start=None, narrowest=None, widest=None, units=None, fmt='%+g' ):
		self.axes = axes
		self.axisname = axisname
		self.start = start
		self.narrowest = narrowest
		self.widest = widest
		self.units = units
		self.fmt = fmt
		self.canZoomOut = True
		self.canZoomIn = True
		self.focusFunction = None
		if self.axisname.lower() in [ 'y', 'vertical' ]:
			self.axisname = 'y'
			self.lims = self.axes.get_ylim()
			self.axis = self.axes.yaxis
		elif self.axisname.lower() in [ 'x', 'horizontal' ]:
			self.axisname = 'x'
			self.lims = self.axes.get_xlim()
			self.axis = self.axes.xaxis
		else:
			raise ValueError( 'unrecognized axisname="%s"' % orientation )
		if self.start == None: self.start = tuple( self.lims )
		if self.units != None: self.axis.set_major_formatter( matplotlib.ticker.FuncFormatter( self.FormatTicks ) )
		self.ChangeAxis( 0.0, start=self.start )
		
	def DrawAxes( self ):
		self.axes.figure.canvas.draw()
		
	def FormatTicks( self, value, index ):
		fudge = 0.001 * ( max( self.lims ) - min( self.lims ) )
		locs = [ x for x in self.axis.get_majorticklocs() if min( self.lims ) - fudge <= x <= max( self.lims ) + fudge ]
		appendUnits = value >= max( locs ) * ( 1 - 1e-8 ) # allow a small tolerance, again to account for precision errors
		return FormatWithUnits( value=value, context=locs, units=self.units, fmt=self.fmt, appendUnits=appendUnits )
	
	def get( self ):
		if   self.axisname == 'x': lims = self.axes.get_xlim()
		elif self.axisname == 'y': lims = self.axes.get_ylim()
		return lims
	
	def set( self, lims ):
		return self.ChangeAxis( direction=0.0, start=lims )

	def ChangeAxis( self, direction=0.0, start=None ):
		lims = list( self.get() )
		if start != None: lims = list( start )
		center = 0.0
		if self.focusFunction:
			roi = self.focusFunction()
			try: roi = list( roi )
			except: roi = [ roi ]
			center = sum( roi ) / float( len( roi ) )
			self.narrowest = [ min( roi ) - ( center - min( roi ) ), max( roi ) + ( max( roi ) - center ) ]
			#ticks = self.axis.get_ticklocs()
			#howclose = [ min( abs( tick - min( roi ) ), abs( tick - max( roi ) ) ) for tick in ticks ]
			#center = ticks[ howclose.index( min( howclose ) ) ]
		lims = [ x - center for x in lims ]
		if lims[ 0 ] < 0.0: lims[ 0 ] = -self.ChangeValue( -lims[ 0 ], direction )
		if lims[ 1 ] > 0.0: lims[ 1 ] = self.ChangeValue( lims[ 1 ], direction )
		lims = [ x + center for x in lims ]
		if self.narrowest != None:
			lims[ 0 ] = min( min( self.narrowest ), lims[ 0 ] )
			lims[ 1 ] = max( max( self.narrowest ), lims[ 1 ] )
			self.canZoomIn = ( lims[ 0 ] < min( self.narrowest ) or lims[ 1 ] > max( self.narrowest ) )
		if self.widest != None:
			lims[ 0 ] = max( min( self.widest ), lims[ 0 ] )
			lims[ 1 ] = min( max( self.widest ), lims[ 1 ] )
			self.canZoomOut = ( lims[ 0 ] > min( self.widest ) or lims[ 1 ] < max( self.widest ) )
		self.lims = tuple( lims )
		if   self.axisname == 'x': self.axes.set_xlim( lims )
		elif self.axisname == 'y': self.axes.set_ylim( lims )
		return self
	
	def Home( self ): return self.ChangeAxis( direction=0.0, start=self.start )
		
	def ChangeValue( self, value, direction ):
		x = 10.0 ** round( math.log10( value ) )
		vals = [ x*0.1, x*0.2, x*0.5, x*1.0, x*2.0, x*5.0, x*10.0 ]
		if direction > 0.0: value = min( x for x in vals if x > value )
		elif direction < 0.0: value = max( x for x in vals if x < value )
		return float( '%.8g' % value ) # crude but effective way of getting rid of nasty numerical precision errors

class PlusMinus( object ):
	def __init__( self, controllers, orientation=None ):
		if not isinstance( controllers, ( tuple, list ) ): controllers = [ controllers ]
		self.controllers = controllers
		if orientation == None: orientation = self.controllers[ 0 ].axisname
		if   orientation.lower() in [ 'y', 'vertical' ]:   self.orientation = 'vertical'
		elif orientation.lower() in [ 'x', 'horizontal' ]: self.orientation = 'horizontal'
		else: raise ValueError( 'unrecognized orientation="%s"' % orientation )
	def ChangeAxis( self, event=None, direction=+1 ):
		if event != None:
			if getattr( event, 'AlreadyHandled', None ) != None: return # don't know why this should be necessary, or how to avoid it in some better way, but hey, this works
			event.AlreadyHandled = 1
		for c in self.controllers: c.ChangeAxis( direction )
		self.Draw()
		return self
	def Enable( self ):
		raise TypeError( 'cannot use the %s superclass - use a subclass instead' % self.__class__.__name__ )
	def Draw( self ):
		plusEnabled = minusEnabled = False
		for c in self.controllers:
			if c.canZoomOut: minusEnabled = True
			if c.canZoomIn:   plusEnabled = True
		self.Enable( self.plusButton, plusEnabled )
		self.Enable( self.minusButton, minusEnabled )
		for c in self.controllers: c.DrawAxes()

class PlusMinusMPL( PlusMinus ):
	def __init__( self, figure, x, y, width, height, controllers, orientation=None, anchor='' ):
		PlusMinus.__init__( self, controllers=controllers, orientation=orientation )
		self.figure = figure
		matplotlib.pyplot.figure( figure.number )
		if self.orientation == 'vertical':
			posMinus = x - width / 2.0, y - height
			posPlus  = x - width / 2.0, y
		else:
			posMinus = x - width, y - height / 2.0
			posPlus  = x, y - height / 2.0
		ax = self.minusAxes = matplotlib.pyplot.axes( posMinus + ( width, height ) )
		ax.set_aspect( 1.0, adjustable='box' )
		ax = self.plusAxes = matplotlib.pyplot.axes( posPlus + ( width, height ) )
		ax.set_aspect( 1.0, adjustable='box' )
		self.SetAnchor( anchor )
		self.plusButton = matplotlib.widgets.Button( self.plusAxes, '+' )
		self.minusButton = matplotlib.widgets.Button( self.minusAxes, u'\u2013' )
		self.plusButton.PlusMinusCallback  = Curry( self.ChangeAxis, direction=-1 )   # that's right, the signs are flipped...
		self.minusButton.PlusMinusCallback = Curry( self.ChangeAxis, direction=+1 )   # ...because people expect the signal to become visually smaller, i.e. for the axes limits to be larger, when '-' is pressed
		self.Enable( self.plusButton, True )
		self.Enable( self.minusButton, True )
	def SetAnchor( self, anchor ):
		if anchor == None or anchor.upper() == 'C': anchor = ''
		if self.orientation == 'vertical':
			self.minusAxes.set_anchor( 'N' + anchor.upper().strip( 'NS' ) )
			self.plusAxes.set_anchor(  'S' + anchor.upper().strip( 'NS' ) )
		else:
			self.minusAxes.set_anchor( anchor.upper().strip( 'EW' ) + 'E' )
			self.plusAxes.set_anchor(  anchor.upper().strip( 'EW' ) + 'W' )
		return self
	def Enable( self, button, state ):
		if state:
			button.CallbackID = button.on_clicked( button.PlusMinusCallback )
			# button.set_axis_bgcolor( ) # TODO: do this, or manipulate the text colour instead?
		else:
			if getattr( button, 'CallbackID', None ) != None: button.disconnect( button.CallbackID )
			button.CallbackID = None
			# button.set_axis_bgcolor( ) # TODO: do this, or grey out the text instead?
		
class PlusMinusTk( PlusMinus ):
	def __init__( self, parent, controllers, orientation=None ):
		PlusMinus.__init__( self, controllers=controllers, orientation=orientation )
		self.parent = parent
		self.frame = tkinter.Frame( parent )
		self.frame[ 'bg' ] = parent[ 'bg' ]
		self.plusButton  = tkinter.Button( self.frame, text='+',       command=Curry( self.ChangeAxis, direction=-1 ) )   # that's right, the signs are flipped...
		self.minusButton = tkinter.Button( self.frame, text=u'\u2013', command=Curry( self.ChangeAxis, direction=+1 ) )   # ...because people expect the signal to become visually smaller, i.e. for the axes limits to be larger, when '-' is pressed
		if self.orientation == 'vertical':
			self.plusButton.place(  relx=0, rely=0, relheight=0.5, relwidth=1.0, anchor='nw' )
			self.minusButton.place( relx=0, rely=1, relheight=0.5, relwidth=1.0, anchor='sw' )
		else:
			self.plusButton.place(  relx=1, rely=0, relheight=1.0, relwidth=0.5, anchor='ne' )
			self.minusButton.place( relx=0, rely=0, relheight=1.0, relwidth=0.5, anchor='nw' )
	def grid( self, *pargs, **kwargs ): self.frame.grid( *pargs, **kwargs ); return self
	def pack( self, *pargs, **kwargs ): self.frame.pack( *pargs, **kwargs ); return self
	def place( self, *pargs, **kwargs ): self.frame.place( *pargs, **kwargs ); return self
	def Enable( self, button, state ): EnableWidget( button, state )

class StickySpanSelector( object ): # definition copied and tweaked from matplotlib.widgets.SpanSelector in matplotlib version 0.99.0
	def __init__( self, ax, onselect=None, initial=None, direction='horizontal', fmt='%+g', units='', minspan=None, granularity=None, useblit=False, **props ):

		if direction not in ['horizontal', 'vertical']: raise ValueError( 'Must choose "horizontal" or "vertical" for direction' )
		self.direction = direction
		self.ax = None
		self.canvas = None
		self.visible = True
		self.cids = []
		self.units = units
		self.fmt = fmt
		self.granularity = granularity
		self.last_moved = 0

		self.rect = None
		self.background = None
		self.pressv = None

		textprops, rectprops = {}, {}
		color = props.pop( 'color', ( 1, 0, 0 ) )
		for k, v in props.items():
			if   k.startswith( 'text_' ): textprops[ k[ 5: ] ] = props.pop( k )
			elif k.startswith( 'rect_' ): rectprops[ k[ 5: ] ] = props.pop( k )
			else: rectprops[ k ] = props.pop( k )
		
		self.rectprops = dict( linewidth=2, edgecolor=color, facecolor=color, alpha=0.4 )
		self.rectprops.update( rectprops )
		self.textprops = dict( color=( 1, 1, 1 ), backgroundcolor=color, x=1.0, y=1.0, verticalalignment='bottom', horizontalalignment='left' )
		self.textprops.update( textprops )
		
		self.onselect = onselect
		self.useblit = useblit
		self.minspan = minspan

		# Needed when dragging out of axes
		self.buttonDown = False
		self.prev = ( 0, 0 )

		self.new_axes(ax)
		self.set( initial )
		
	def sibs( self ):
		attr = self.direction + 'StickySpanSelectors'
		if not hasattr( self.ax, attr ): setattr( self.ax, attr, [] )
		return getattr( self.ax, attr )
				
	def new_axes( self, ax ):
		self.ax = ax
		self.sibs().append( self )
		if self.canvas is not ax.figure.canvas:
			for cid in self.cids:
				self.canvas.mpl_disconnect( cid )
			self.canvas = ax.figure.canvas
			self.cids.append( self.canvas.mpl_connect( 'motion_notify_event', self.onmove ) )
			self.cids.append( self.canvas.mpl_connect( 'button_press_event', self.press ) )
			self.cids.append( self.canvas.mpl_connect( 'button_release_event', self.release ) )
			self.cids.append( self.canvas.mpl_connect( 'draw_event', self.update_background ) )
			self.cids.append( self.canvas.mpl_connect( 'key_press_event', self.keypress ) )
		if self.direction == 'horizontal':
			trans = self.ax.get_xaxis_transform()
			self.rect = matplotlib.patches.Rectangle( ( 0, -0.01 ), 0, 1.02, transform=trans, visible=False, **self.rectprops )
		else:
			trans = self.ax.get_yaxis_transform()
			self.rect = matplotlib.patches.Rectangle( ( -0.01, 0 ), 1.02, 0, transform=trans, visible=False, **self.rectprops )
			
		if not self.useblit: self.ax.add_patch( self.rect )
		self.mintext = self.ax.text( s='min', transform=trans, **self.textprops )
		self.maxtext = self.ax.text( s='max', transform=trans, **self.textprops )
		self.update_text()
	
	def keypress( self, event ):
		if self.ax is not self.ax.figure.gca(): return True
		if self is not self.sibs()[ -1 ]: return True
		if event.key == None: return True
		coords = list( self.get() )
		gran = self.granularity
		arrow = str( event.key ).split( '+' )[ -1 ]
		if gran == None: minv, maxv = self.get(); gran = max( abs( maxv ), abs( minv ) ) / 100.0
		if   arrow in [ 'left'  ] and self.direction == 'horizontal': coords[ self.last_moved ] -= gran
		elif arrow in [ 'right' ] and self.direction == 'horizontal': coords[ self.last_moved ] += gran
		elif arrow in [ 'down'  ] and self.direction == 'vertical':   coords[ self.last_moved ] -= gran
		elif arrow in [ 'up'    ] and self.direction == 'vertical':   coords[ self.last_moved ] += gran
		elif arrow in [ 'enter' ]:
			attr = self.direction + 'StickySpanSelectorKeyPressHandled'
			previouslyHandled = getattr( event, attr, False )
			setattr( event, attr, True )
			if not previouslyHandled:
				self.last_moved += 1
				if self.last_moved > 1:
					self.last_moved = 0
					sibs = self.sibs()
					sibs.remove( self )
					sibs.insert( 0, self )
					sibs[ -1 ].last_moved = 0
			return True
		else: return True
		if coords[ 1 ] < coords[ 0 ]: self.last_moved = 1 - self.last_moved
		self.set( coords )
		return False
	
	def get( self ):
		if self.direction == 'horizontal':
			start = self.rect.get_x()
			extent = self.rect.get_width()
		else:
			start = self.rect.get_y()
			extent = self.rect.get_height()
		return ( start, start + extent )
		
	def set( self, span, trigger_callback=True ):
		if span == None:
			self.rect.set_visible( False )
			self.mintext.set_visible( False )
			self.maxtext.set_visible( False )
		else:
			self.rect.set_visible( self.visible )
			self.mintext.set_visible( self.visible )
			self.maxtext.set_visible( self.visible )
			vmin, vmax = min( span ), max( span )
			if self.direction == 'horizontal':
				self.rect.set_x( vmin )
				self.rect.set_width( vmax - vmin )
			else:
				self.rect.set_y( vmin )
				self.rect.set_height( vmax - vmin )
			if trigger_callback and self.onselect: self.onselect( vmin, vmax )
			self.update_text()
		self.update()
		self.canvas.draw()

	def update_background(self, event):
		'force an update of the background'
		if self.useblit:
			self.background = self.canvas.copy_from_bbox( self.ax.bbox )

	def ignore( self, event, v ):
		'return True if event should be ignored'
		if event.inaxes != self.ax or not self.visible or event.button != 1: return True
		sibs = self.sibs()
		nearest = None
		dmin = None
		for sib in self.sibs():
			d = min( abs( lim - v ) for lim in sib.get() )
			if dmin == None or d < dmin: dmin = d; nearest = sib
		return ( self is not nearest )

	def focus( self ):
		sibs = self.sibs()
		sibs.remove( self )
		sibs.append( self )
		self.ax.figure.sca( self.ax )
		try: self.ax.figure.canvas._tkcanvas.focus_set()
		except: pass
		
	def press( self, event ):
		'on button press event'
		if self.direction == 'horizontal': v = event.xdata
		else:                              v = event.ydata
			
		if self.ignore( event, v ): return
		self.buttonDown = True
		self.rect.set_visible( self.visible )
		
		span = self.get()
		if abs( v - min( span ) ) < abs( v - max( span ) ): self.pressv = max( span ); self.last_moved = 0
		else:                                               self.pressv = min( span ); self.last_moved = 1
		self.focus()
		return self.onmove( event ) # if you press and hold without moving, the line still responds
		
	def release( self, event ):
		'on button release event'
		
		vmin = self.pressv
		if self.direction == 'horizontal': vmax = event.xdata or self.prev[ 0 ]
		else:                              vmax = event.ydata or self.prev[ 1 ]

		if vmin is None or vmax is None or not self.buttonDown: return
		self.buttonDown = False

		if vmin > vmax: vmin, vmax = vmax, vmin
		vmin = self.round( vmin )
		vmax = self.round( vmax )
		span = vmax - vmin
		if self.minspan is not None and span < self.minspan:
			print 'TODO' # TODO: it's not enough to just return here: need to actually move the boundaries
		self.set( ( vmin, vmax ) )
		self.pressv = None
		return False

	def onmove( self, event ):
		'on motion notify event'
		x, y = event.xdata, event.ydata
		if self.direction == 'horizontal': v = x
		else:                              v = y
		if self.pressv is None or v is None or not self.buttonDown: return
		self.prev = x, y
		self.set( ( self.round( v ), self.round( self.pressv ) ), trigger_callback=False )
		return False

	def update( self ):
		'draw using newfangled blit or oldfangled draw depending on useblit'
		if self.useblit:
			if self.background is not None: self.canvas.restore_region( self.background )
			self.ax.draw_artist( self.rect )
			self.canvas.blit( self.ax.bbox )
		else:
			self.canvas.draw_idle()
		return False

	def update_text( self ):
		minv, maxv = self.get()
		context = self.axislimits()
		minvtext = FormatWithUnits( value=minv, context=context, units=self.units, fmt=self.fmt )
		maxvtext = FormatWithUnits( value=maxv, context=context, units=self.units, fmt=self.fmt )
		if self.direction == 'horizontal':
			self.mintext.set( x=minv, text=minvtext, visible=self.visible, horizontalalignment='right' )
			self.maxtext.set( x=maxv, text=maxvtext, visible=self.visible, horizontalalignment='left' )
		else:
			self.mintext.set( y=minv, text=minvtext, visible=self.visible, verticalalignment='top' )
			self.maxtext.set( y=maxv, text=maxvtext, visible=self.visible, verticalalignment='bottom' )
			
	def axislimits( self ):
		if self.direction == 'horizontal': return self.ax.get_xlim()
		else:                              return self.ax.get_ylim()
			
	def round( self, value ):
		gran = self.granularity
		#lims = self.axislimits()
		#gran = max( abs( x ) for x in lims ) * self.granularity
		if not gran: return value
		return gran * round( value / gran )

class TkMPL( object ):
	
	def __init__( self ):
		self.artists = Bunch()
		self.widgets = Bunch()
		self.colors = Bunch(
			           figure = '#CCCCCC',
			               bg = '#CCCCCC',
			               fg = '#000000',
			           button = '#DDDDDD',
			         disabled = '#777777',
			         backpage = '#888888',
			           header = '#CCCCCC',
			           footer = '#DDDDDD',
			             emg1 = '#0000FF',
			             emg2 = '#FF0000',
			             good = '#008800',
			              bad = '#FF0000',
			         error_bg = '#AA0000',
			  error_highlight = '#FF6666',
			       warning_bg = '#886600',
			warning_highlight = '#AA8800',
		)

	def Match( self, things, *terms ):
		keys = []
		matches = []
		for key, thing in things.items():
			keyparts = key.lower().split( '_' )
			for match_term in terms:
				if match_term.lower() not in keyparts: break
			else:
				keys.append( key )
				matches.append( thing )
		return keys, matches
		
	def MatchArtists( self, *terms ):
		keys, things = self.Match( self.artists, *terms )
		return things
		
	def MatchWidgets( self, *terms ):
		keys, things = self.Match( self.widgets, *terms )
		return things
		
	def DrawFigures( self, *terms ):
		for fig in self.MatchArtists( 'figure', *terms ): fig.canvas.draw()
			
	def NewFigure( self, parent, prefix, suffix, fig=None, color=None, **kwargs ):
		name = prefix + '_figure_' + suffix
		if fig: matplotlib.pyplot.figure( fig.number )
		else: fig = matplotlib.pyplot.figure()
		container = tkinter.Frame( parent, bg=parent[ 'bg' ] )
		matplotlib.backends.backend_tkagg.FigureCanvasTkAgg( fig, master=container) # replaces fig.canvas
		widget = fig.canvas.get_tk_widget()
		if color == None: color = self.colors.figure
		if color == None: color = widget.master[ 'bg' ]
		fig.patch.set_edgecolor( color )
		fig.patch.set_facecolor( color )
		widget.configure( bg=color, borderwidth=0, insertborderwidth=0, selectborderwidth=0, highlightthickness=0, insertwidth=0 )
		container.configure( width=800, height=600 )
		if len( kwargs ): container.configure( **kwargs )
		FixAspectRatio( widget ) #, relx=0.0, anchor='w' )
		self.artists[ name ] = fig
		self.widgets[ name ] = widget
		fig.subplots_adjust( bottom=0.06, top=0.94, right=0.92 )
		return fig, widget, container

class GUI( tksuperclass, TkMPL ):
	
	def __init__( self, operator=None ):
		
		tksuperclass.__init__( self )
		TkMPL.__init__( self )

		try: tkinter.ALLWINDOWS # TODO: remove this section
		except: tkinter.ALLWINDOWS = []
		tkinter.ALLWINDOWS.append( self )
		
		self.option_add( '*Font', 'TkDefaultFont 13' )
		self.option_add( '*Label*Font', 'TkDefaultFont 13' )
		
		self.ready = False
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
		self.afterIDs = {}
		self.messages = Bunch()
		self.states = Bunch( st=Bunch(), vc=Bunch(), rc=Bunch(), ct=Bunch(), tt=Bunch() )
		self.data = Bunch( st=[], vc=[], rc=[], ct=[], tt=[] )
		self.threads = Bunch()
		self.keepgoing = True
		self.mode = None
		
		self.footer_location = 'top'
		self.settings_location = 'left'

		if operator == None: operator = Operator()
		self.operator = operator
		
		self.inifile = os.path.join( GUIDIR, 'epocs.ini' )
		if os.path.isfile( self.inifile ):
			self.operator.Set( **eval( open( self.inifile, 'rt' ).read() ) )		
		
		if DEVEL: self.bind( "<Escape>", self.destroy )
		if not SubjectChooser( self, initialID=self.operator.params.SubjectName ).successful: self.destroy(); return		
		WriteDict( self.operator.params, self.inifile, 'SubjectName', 'DataDirectory' )
		
		label = tkinter.Label( self, text='Launching BCI2000 system...', font=( 'Helvetica', 15 ) )
		label.grid( row=1, column=1, sticky='nsew', padx=100, pady=100 )
		self.update()
		label.destroy()
		
		self.protocol( 'WM_DELETE_WINDOW', self.CloseWindow )
		self.operator.Launch()
		self.operator.SetConfig( work_around_bci2000_bug=True )
		self.GetSignalParameters()
		
		if 'ttk' in sys.modules:
			notebook = self.widgets.notebook = ttk.Notebook( self )
		else:
			notebook = self.widgets.notebook = Tix.NoteBook( self, name='notebook', ipadx=6, ipady=6 )
			notebook[ 'bg' ] = notebook.nbframe[ 'bg' ] = self.colors.bg
			notebook.nbframe[ 'backpagecolor' ] = self.colors.backpage
		
		notebook.pack( expand=1, fill='both', padx=5, pady=5 ,side='top' )
		
		self.modenames = Bunch( st='Stimulus Test', vc='Voluntary Contraction', rc='Recruitment Curve', ct='Control Trials', tt='Training Trials' )
		
		v = self.operator.params._TraceLimitVolts
		self.axiscontrollers_emg1 = []
		self.axiscontrollers_emg2 = []
		
		matplotlib.pyplot.close( 'all' )
		
		frame = self.AddTab( 'st', title=self.modenames.st )
		fig, widget, container = self.NewFigure( parent=frame, prefix='st', suffix='emg' )
		self.FooterFrame( 'st', analysis=False )
		self.HeaderFrame( 'st', success=False )
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
		
		
		frame = self.AddTab( 'vc', title=self.modenames.vc )
		fig, widget, container = self.NewFigure( parent=frame, prefix='vc', suffix='emg' )
		self.FooterFrame( 'vc' )
		self.HeaderFrame( 'vc', trials=False, success=False )
		self.NewBar( parent=frame, figure=fig, axes=( 1, 2, 1 ), prefix='vc', suffix='background', title='Muscle Activity' )
		container.pack( side='top', fill='both', expand=True, padx=20, pady=5 )
		frame.pack( side='left', padx=2, pady=2, fill='both', expand=1 )

		
		frame = self.AddTab( 'rc', title=self.modenames.rc )
		fig, widget, container = self.NewFigure( parent=frame, prefix='rc', suffix='emg' )
		self.FooterFrame( 'rc' )
		self.HeaderFrame( 'rc', success=False )
		self.NewBar( parent=frame, figure=fig, axes=( 1, 2, 1 ), prefix='rc', suffix='background', title='Muscle Activity' )
		ax1 = self.artists.rc_axes_emg1 = matplotlib.pyplot.subplot( 2, 2, 2 )
		self.artists.rc_line_emg1 = matplotlib.pyplot.plot( ( 0, 0 ), ( 0, 0 ), color=self.colors.emg1 )[ 0 ]
		ax1.grid( True )
		self.axiscontrollers_emg1.append( AxisController(  ax1, 'y', units='V', start=( -v[ 0 ], +v[ 0 ] ), narrowest=( -0.0001, +0.0001 ), widest=( -20.000, +20.000 ) ) )
		self.widgets.rc_yadjust_emg1 = PlusMinusTk( parent=frame, controllers=self.axiscontrollers_emg1 ).place( in_=widget, width=20, height=40, relx=0.93, rely=0.25, anchor='w' ) # rely=0.75 for subplot( 2, 2, 4 ) only, or rely=0.25 for subplot( 2, 2, 2 ) only / both
		ax2 = self.artists.rc_axes_emg2 = matplotlib.pyplot.subplot( 2, 2, 4 )
		self.artists.rc_line_emg2 = matplotlib.pyplot.plot( ( 0, 0 ), ( 0, 0 ), color=self.colors.emg2 )[ 0 ]
		ax2.grid( True )
		self.axiscontrollers_emg2.append( AxisController(  ax2, 'y', units='V', start=( -v[ 1 ], +v[ 1 ] ), narrowest=( -0.0001, +0.0001 ), widest=( -20.000, +20.000 ) ) )
		self.widgets.rc_yadjust_emg2 = PlusMinusTk( parent=frame, controllers=self.axiscontrollers_emg2 ).place( in_=widget, width=20, height=40, relx=0.93, rely=0.75, anchor='w' ) # rely=0.75 for subplot( 2, 2, 4 ) only, or rely=0.25 for subplot( 2, 2, 2 ) only / both
		self.widgets.rc_xadjust_emg  = PlusMinusTk( parent=frame, controllers=[ AxisController( ax, 'x', units='s', start=( -0.020, +0.100 ), narrowest=( -0.002,  +0.010  ), widest=( -0.100, +0.500 ) ) for ax in self.MatchArtists( 'rc', 'axes' ) ] ).place( in_=widget, width=40, height=20, relx=0.92, rely=0.05, anchor='se' ) # rely=0.52 for subplot( 2, 2, 4 ) only, or rely=0.06 for subplot( 2, 2, 2 ) only / both
		container.pack( side='top', fill='both', expand=True, padx=20, pady=5 )
		frame.pack( side='left', padx=2, pady=2, fill='both', expand=1 )


		frame = self.AddTab( 'ct', title=self.modenames.ct )
		fig, widget, container = self.NewFigure( parent=frame, prefix='ct', suffix='emg' )
		self.FooterFrame( 'ct' )
		self.HeaderFrame( 'ct', success=False )
		self.NewBar( parent=frame, figure=fig, axes=( 1, 2, 1 ), prefix='ct', suffix='background', title='Muscle Activity' )
		container.pack( side='top', fill='both', expand=True, padx=20, pady=5 )
		frame.pack( side='left', padx=2, pady=2, fill='both', expand=1 )

		
		frame = self.AddTab( 'tt', title=self.modenames.tt )
		fig, widget, container = self.NewFigure( parent=frame, prefix='tt', suffix='emg' )
		self.FooterFrame( 'tt' )
		self.HeaderFrame( 'tt', success=True )
		self.NewBar( parent=frame, figure=fig, axes=( 1, 2, 1 ), prefix='tt', suffix='background', title='Muscle Activity' )
		self.NewBar( parent=frame, figure=fig, axes=( 1, 2, 2 ), prefix='tt', suffix='response', title='Response' )
		self.artists.tt_line_baseline = matplotlib.pyplot.plot( ( 0, 1 ), ( -1, -1 ), color='#000088', alpha=0.7, linewidth=4, transform=fig.gca().get_yaxis_transform() )[ 0 ]
		container.pack( side='top', fill='both', expand=True, padx=20, pady=5 )
		frame.pack( side='left', padx=2, pady=2, fill='both', expand=1 )


		tab = self.AddTab( 'log', title='Log', makeframe=False )
		logfile = self.operator.LogFile( autoCreate=True )
		frame = self.widgets.log_scrolledtext = ScrolledText( parent=tab, filename=logfile, font='{Courier} 12', bg='#FFFFFF' )
		frame.pack( side='top', padx=2, pady=2, fill='both', expand=1 )
		
		
		self.SetBarLimits( 'vc', 'rc', 'ct', 'tt' )
		self.SetTargets(   'vc', 'rc', 'ct', 'tt' )
		self.DrawFigures()
		#self.resizable( True, False ) # STEP 13 from http://sebsauvage.net/python/gui/
		self.update(); self.geometry( self.geometry().split( '+', 1 )[ 0 ] + '+25+25' ) # prevents Tkinter from resizing the GUI when component parts try to change size (STEP 18 from http://sebsauvage.net/python/gui/ )
		self.wm_state( 'zoomed' )
		self.ready = True

	def AddTab( self, key, title, makeframe=True ):
		if 'ttk' in sys.modules:
			tab = self.widgets[ key + '_tab' ] = tkinter.Frame( self, bg=self.colors.bg )
			tab.pack()
			self.widgets.notebook.add( tab, text=' ' + title + ' ', underline=1, padding=10 )
			if not makeframe: return tab
			frame = self.widgets[ key + '_frame_main'] = tkinter.Frame( tab, bg=self.colors.bg )
			return frame
		else:
			tab   = self.widgets[ key + '_tab' ] = self.widgets.notebook.add( name=key + '_tab', label=title, underline=0 )
			tab[ 'bg' ] = self.colors.bg
			if not makeframe: return tab
			frame = self.widgets[ key + '_frame_main' ] = tkinter.Frame( tab, bg=self.colors.bg )
			return frame
		
	def TabFocus( self, whichTab='all' ):
		tabNames = [ k for k in self.widgets.keys() if 'tab' in k.lower().split( '_' ) ]
		for tabName in tabNames:
			if whichTab == 'all' or whichTab.lower() in tabName.lower().split( '_' ): state = 'normal'
			else: state = 'disabled'
			if 'ttk' in sys.modules: self.widgets.notebook.tab( self.widgets[ tabName ], state=state )
			else: self.widgets.notebook.tk.call( self.widgets.notebook._w, 'pageconfigure', tabName, '-state', state )
	
	def GetSignalParameters( self ):
		self.fs = float( self.operator.remote.GetParameter( 'SamplingRate' ).lower().strip( 'hz' ) )
		self.sbs = float( self.operator.remote.GetParameter( 'SampleBlockSize' ) )
		self.lookback = float( self.operator.params.LookBack.strip( 'ms' ) ) / 1000.0
		
	def Start( self, mode ):
		self.run = 'R%02d' % self.operator.NextRunNumber() # must query this before starting the run
		self.operator.Start( mode.upper() )
		self.TabFocus( mode )
		EnableWidget( self.MatchWidgets( mode, 'button' ), False )
		EnableWidget( self.MatchWidgets( mode, 'button', 'stop' ), True )
		self.mode = mode
		for w in self.MatchWidgets( mode, 'label', 'value', 'trial' ): w.config( text='0' )
		for w in self.MatchWidgets( mode, 'label', 'value', 'success' ): w.config( text='---', fg='#000000' )
		for w in self.MatchWidgets( mode, 'label', 'title', 'run' ): w.config( text='Now Recording:' )
		for w in self.MatchWidgets( mode, 'label', 'value', 'run' ): w.config( text=self.run )
		self.states[ mode ] = Bunch()
		self.data[ mode ] = []
		self.GetSignalParameters()
		self.block = {}
		self.NewTrial( [ [ 0 ], [ 0 ], [ 0 ], [ 0 ] ], store=False )
		self.SetBarLimits( mode )
		self.SetTargets( mode )
		self.UpdateBar( 0.0, True, mode )
		if not self.widgets.log_scrolledtext.filename:
			self.widgets.log_scrolledtext.load( self.operator.LogFile( autoCreate=True ) )
		self.Log( '\n', datestamp=False )
		self.Log( 'Started run %s (%s)' % ( self.run, self.modenames[ self.mode ] ) )
	
	def Stop( self ):
		self.operator.Stop()
		self.TabFocus( 'all' )
		EnableWidget( self.MatchWidgets( self.mode, 'button' ), True )
		EnableWidget( self.MatchWidgets( self.mode, 'button', 'stop' ), False )
		EnableWidget( self.MatchWidgets( self.mode, 'button', 'analysis' ), len( self.data[ self.mode ] ) > 0 )
		for w in self.MatchWidgets( 'label', 'title', 'run' ): w.config( text='Last Recording:' )
		msg = ''
		if self.mode not in [ 'vc' ]: msg = ' after %d trials' % len( self.data[ self.mode ] )
		self.Log( 'Stopped run %s%s' % ( self.run, msg ) )
		self.mode = None
		self.run = None
	
	def SetBarLimits( self, *modes ):
		for mode in modes:
			for a in self.MatchArtists( mode, 'axiscontroller', 'background' ):
				a.ChangeAxis( start=( 0, self.operator.GetVolts( self.operator.GetBackgroundBarLimit( mode ) ) ) )
				self.NeedsUpdate( a.axes.figure )
			for a in self.MatchArtists( mode, 'axiscontroller', 'response' ):
				a.ChangeAxis( start=( 0, self.operator.GetVolts( self.operator.params._ResponseBarLimit ) ) )
				self.NeedsUpdate( a.axes.figure )
			for a in self.MatchArtists( mode, 'line', 'baseline' ):
				val = self.operator.GetVolts( self.operator.params._BaselineResponse ) 
				if val == None: val = -1
				a.set_ydata( ( val, val ) )
				self.NeedsUpdate( a.axes.figure )
				
	def SetTargets( self, *modes ):
		for mode in modes:
			if mode in [ 'rc', 'ct', 'tt' ]:
				min, max = self.operator.GetVolts( ( self.operator.params._BackgroundMin[ 0 ], self.operator.params._BackgroundMax[ 0 ] ) )
				self.UpdateTarget( min, max, mode, 'target', 'background' )
				min, max = self.operator.GetVolts( ( self.operator.params._ResponseMin[ 0 ], self.operator.params._ResponseMax[ 0 ] ) )
				self.UpdateTarget( min, max, mode, 'target', 'response' ) # TODO: UpdateTarget will need to deal with Nones

	def SettingsFrame( self, code, settings=True, analysis=True ):
		if settings: settings_tag = '_button_settings'
		else: settings_tag = '_fakebutton_settings'
		if analysis: analysis_tag = '_button_analysis'
		else: analysis_tag = '_fakebutton_analysis'
		parent = self.widgets[ code + '_frame_footer' ]
		frame = self.widgets[ code + '_frame_settings' ] = tkinter.Frame( parent, bg=parent[ 'bg' ] )
		button = self.widgets[ code + analysis_tag ] = tkinter.Button( frame, text='Analysis', command = Curry( AnalysisWindow, parent=self, mode=code ) )
		EnableWidget( button, False )
		button.pack( side='top', ipadx=20, padx=2, pady=2, fill='both' )
		button = self.widgets[ code + settings_tag ]    = tkinter.Button( frame, text='Settings',    command = Curry( SettingsWindow, parent=self, mode=code ) )
		EnableWidget( button, settings )
		button.pack( side='bottom', ipadx=20, padx=2, pady=2, fill='both' )
		frame.pack( side=self.settings_location, fill='y', padx=5 )
		
	def InfoFrame( self, code, name, title, value, size=14, labelsize=10, parent=None, color='#000000' ):
		if parent == None: parent = self.widgets[ code + '_frame_footer' ]
		frame = self.widgets[ code + '_frame_info_' + name ] = tkinter.Frame( parent, bg=parent[ 'bg' ] )
		tLabel = self.widgets[ code + '_label_title_' + name ] = tkinter.Label( frame, text=title, font=( 'Helvetica', labelsize ), bg=parent[ 'bg' ], fg=color )
		vLabel = self.widgets[ code + '_label_value_' + name ] = tkinter.Label( frame, text=value, font=( 'Helvetica', size ),      bg=parent[ 'bg' ], fg=color )
		tLabel.pack( side='top', fill='both', padx=2, pady=2, expand=1 )
		vLabel.pack( side='bottom', fill='both', padx=2, pady=4, expand=1 )
		return frame
		
	def HeaderFrame( self, code, trials=True, success=False ):
		tabkey = code + '_tab'
		tab = self.widgets[ code + '_tab' ]
		frame = self.widgets[ code + '_frame_header' ] = tkinter.Frame( tab, bg=self.colors.header )
		if trials: self.InfoFrame( code, 'trial', 'Trials Completed:', '0', parent=frame, labelsize=20, size=70 ).place( relx=0.5, rely=0.1, anchor='n' )
		bg = frame[ 'bg' ]
		display = '----'
		#bg = '#FF0000'; display = '99.9%'  # for debugging
		tkinter.Frame( frame, width=420, height=2, bg=bg ).pack( side='bottom' ) # spacer
		if success: self.InfoFrame( code, 'success', 'Success Rate:', display, parent=frame.master, labelsize=20, size=110 ).place( in_=frame, relx=0.5, rely=0.9, anchor='s' )
		#frame.grid( row=1, column=2, sticky='nsew' )
		frame.pack( side='right', fill='y' )
		return frame
		
	def FooterFrame( self, code, **kwargs ):
		tabkey = code + '_tab'
		tab = self.widgets[ code + '_tab' ]
		frame = self.widgets[ code + '_frame_footer' ] = tkinter.Frame( tab, bg=self.colors.footer )
		button = self.widgets[ code + '_button_start' ] = tkinter.Button( frame, text='Start', command = Curry( self.Start, mode=code ) )
		button.pack( side='left', ipadx=20, ipady=20, padx=2, pady=2, fill='y' )
		button = self.widgets[ code + '_button_stop'  ] = tkinter.Button( frame, text='Stop',  command = self.Stop, state='disabled' )
		button.pack( side='left', ipadx=20, ipady=20, padx=2, pady=2, fill='y' )
		self.SettingsFrame( code, **kwargs )
		self.InfoFrame( code, 'subject', 'Patient ID:', self.operator.params.SubjectName ).pack( side='left', fill='y', padx=5, pady=2, expand=1 )
		self.InfoFrame( code, 'session', 'Session Started At:', self.operator.FriendlyDate() ).pack( side='left', fill='y', padx=5, pady=2, expand=1 )
		lastRun = self.operator.LastRunNumber( mode=code )
		if lastRun: lastRun = 'R%02d' % lastRun
		else: lastRun = '---'
		self.InfoFrame( code, 'run', 'Last Recording:', lastRun ).pack( side='left', fill='y', padx=5, pady=2, expand=1 )
		frame.pack( side=self.footer_location, fill='x', padx=2, pady=2 )
		#frame.grid( row=2, column=1, columnspan=2, sticky='nsew' )
		return frame
	
	def NewBar( self, parent, prefix, suffix, figure=None, axes=None, **kwargs ):
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
		if self.footer_location == 'top': xlabel, title = title, xlabel
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
		if fig not in self.pendingFigures:
			self.pendingFigures.append( fig )
			
	def UpdateTarget( self, min, max, *terms ):
		for target in self.MatchArtists( 'target', *terms ):
			if min == None: min = 0.0
			if max == None: max = target.axes.get_ylim()[ 1 ]
			target.set( y=min, height=max - min )
			self.NeedsUpdate( target.figure )
		
	def UpdateBar( self, height, good, *terms ):
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
		old = self.afterIDs.get( key, None )
		if old != None: self.after_cancel( old )
		self.afterIDs[ key ] = self.after( msec, func )
	
	def CloseWindow( self ):
		if self.mode == None: self.destroy()
		
	def destroy( self, arg=None ):
		self.StopThreads()
		if getattr( self, 'operator', None ):
			con1 = getattr( self, 'axiscontrollers_emg1', [ None ] )[ 0 ]
			if con1: self.operator.params._TraceLimitVolts[ 0 ] = max( con1.get() )
			con2 = getattr( self, 'axiscontrollers_emg2', [ None ] )[ 0 ]
			if con2: self.operator.params._TraceLimitVolts[ 1 ] = max( con2.get() )
			if self.operator.sessionStamp:
				try: self.operator.WriteSettings()
				except: pass
			self.operator.bci2000( 'quit' )
			
		if getattr( self, 'afterIDs', None ):
			for k in self.afterIDs.keys():
				self.after_cancel( self.afterIDs.pop( k ) )
		try: tksuperclass.destroy( self )
		except: pass
		self.quit()
	
	def Log( self, text, datestamp=True ):
		if datestamp: stamp = self.operator.FriendlyDate( time.time() ) + '       '
		else: stamp = ''
		self.widgets.log_scrolledtext.append( stamp + text + '\n', ensure_newline_first=True )
	
	def ScheduleTask( self, key, func ):
		self.pendingTasks[ key ] = func
		
	def DrawPendingFigures( self ):
		
		for v in self.pendingTasks.values(): v()
		self.pendingTasks.clear()
			
		while len( self.pendingFigures ):
			fig = self.pendingFigures.pop( 0 )
			while fig in self.pendingFigures: self.pendingFigures.remove( fig )
			fig.canvas.draw()
		self.After( 10, 'DrawPendingFigures', self.DrawPendingFigures )

	def StopThreads( self ):
		self.keepgoing = False
	
	def WatchMM( self ):
		counter = prev = 0
		while self.keepgoing:
			while self.keepgoing and ( counter == prev or counter == 0 ):
				time.sleep( 0.001 )
				counter = self.operator.MMCounter()
			if self.keepgoing:
				prev = counter
				signal, states = self.operator.ReadMM()
				if self.Incoming( states, 'States' ):
					self.Incoming( signal, 'Signal' )
		
	def Incoming( self, block, queue ):
		
		code = self.mode
		if code == None: return False
		states = self.states[ code ]
		
		if block == None: return False
		
		if queue == 'Signal':
			self.NewTrial( block )
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
			self.ScheduleTask( 'update_background', Curry( self.UpdateBar, height, good, code, 'background' ) )
				
		if changed.ResponseFeedbackValue or changed.ResponseGreen:
			height = states.ResponseFeedbackValue / 1000000.0
			good = ( states.ResponseGreen != 0.0 )
			#print 'received.append(%g)' % height # TODO
			self.ScheduleTask( 'update_response',   Curry( self.UpdateBar, height, good, code, 'response' ) )
		
		if changed.TrialsCompleted:
			trialCounter = self.widgets.get( code + '_label_value_trial', None )
			successCounter = self.widgets.get( code + '_label_value_success', None )
			if trialCounter != None:
				trialCounter.configure( text='%d' % states.TrialsCompleted )
			
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
				
	def	NewTrial( self, signal, store=True ):
		if signal == None: return
		if store and self.mode not in [ 'vc' ]: self.data[ self.mode ].append( signal )
		for channelIndex, values in enumerate( signal ):
			lines = self.MatchArtists( self.mode, 'line', 'emg' + str( channelIndex + 1 ) )
			if len( lines ) == 0: continue
			line = lines[ 0 ]
			line.set( xdata=TimeBase( values, self.fs, self.lookback ), ydata=values )
			self.NeedsUpdate( line.figure )
				
	def StartThread( self, name, func, *pargs, **kwargs ):
		t = self.threads[ name ] = threading.Thread( target=func, args=pargs, kwargs=kwargs )
		t.start()

	def Loop( self ):
		self.keepgoing = True
		self.StartThread( 'watch_mm', self.WatchMM )
		self.After( 50, 'DrawPendingFigures', self.DrawPendingFigures )
		try: self.mainloop()
		except KeyboardInterrupt: pass
		self.StopThreads()
		

class Dialog( tkinter.Toplevel ):
	""" Modal dialog box courtesy of Fredrik Lundh: http://effbot.org/tkinterbook/tkinter-dialog-windows.htm """
	def __init__( self, parent, title=None, icon=None, geometry=None ):

		tkinter.Toplevel.__init__( self, parent )
		self.transient( parent )
		if title: self.title( title )
		if icon: self.iconbitmap( icon )
		self.parent = parent
		self.result = None
		body = tkinter.Frame( self )
		self.initial_focus = self.body( body )
		body.pack( side='top', fill='both', expand=True, padx=5, pady=5 )
		self[ 'bg' ] = body[ 'bg' ]
		self.buttonbox()
		self.grab_set()
		if not self.initial_focus: self.initial_focus = self
		self.protocol( "WM_DELETE_WINDOW", self.cancel )
		if geometry == None: geometry = "+%d+%d" % ( parent.winfo_rootx() + 10, parent.winfo_rooty() + 30 )
		self.geometry( geometry )
		self.initial_focus.focus_set()
		self.wait_window( self )

	# construction hooks

	def body( self, master ): pass  # create dialog body. return widget that should have initial focus. this method should be overridden
	
	def buttonbox( self ):
		# add standard button box. override if you don't want the
		# standard buttons
		self.footer = tkinter.Frame( self, bg=self[ 'bg' ] )
		w = tkinter.Button( self.footer, text="OK", width=10, command=self.ok, default=tkinter.ACTIVE )
		w.pack( side=tkinter.LEFT, padx=5, pady=5 )
		w = tkinter.Button( self.footer, text="Cancel", width=10, command=self.cancel )
		w.pack( side=tkinter.LEFT, padx=5, pady=5 )
		self.bind( "<Return>", self.ok )
		self.bind( "<Escape>", self.cancel )
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
		self.parent.focus_set()
		#print self.geometry()
		self.destroy()

	# command hooks
	def validate(self): return True # override
	def apply(self): pass # override
		
class ScrolledText( tkinter.Frame ):
	"""Adapted from Stephen Chappell's post at http://code.activestate.com/recipes/578569-text-editor-in-python-33/ """
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
		open( self.filename, 'wt' ).write( text )
		self.text.edit_separator()
		self.saved = text
	def destroy( self ):
		self.after_cancel( self.after_id )
		self.autosave()
		tkinter.Frame.destroy( self )
	def load( self, filename ):
		self.autosave()
		text = open( filename, 'rt' ).read()
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

def ResponseMagnitudes( data, channel, interval, fs, lookback, p2p=False ):
	interval = min( interval ), max( interval )
	r = []
	for trial in data:
		y = trial[ channel ]
		start, length = interval[ 0 ], interval[ 1 ] - interval[ 0 ]
		start  = round( ( start + lookback ) * fs )
		length = round( length * fs )
		y = [ yi for i, yi in enumerate( y ) if start <= i < start + length ]
		if p2p: r.append( max( y ) - min( y ) )
		else: r.append( sum( abs( yi ) for yi in y ) / float( len( y ) ) )
	return r

def Quantile( x, q, alreadySorted=False ):
	if not alreadySorted: x = sorted( x )
	if isinstance( q, ( tuple, list ) ): return [ Quantile( x, qi, alreadySorted=True ) for qi in q ]
	n = ( len( x ) + 1 ) * q - 1
	up = int( math.ceil( n ) )
	lo = int( math.floor( n ) )
	#if lo < 0 or up >= len( x ): return None
	if lo < 0: return x[ 0 ]
	if up >= len( x ): return x[ -1 ]
	if up == lo: return x[ lo ]
	return x[ lo ] * ( up - n ) + x[ up ] * ( n - lo )

class MVC( object ):
	def __init__( self, data, fs, axes=None, callback=None ):
		if axes == None: axes = matplotlib.pyplot.gca()
		else: matplotlib.pyplot.figure( axes.figure.number ).sca( axes )
		self.axes = axes
		self.data = data
		self.fs = fs
		self.time = TimeBase( self.data, fs=self.fs, lookback=0 )
		self.line = matplotlib.pyplot.plot( self.time, self.data )[ 0 ]
		self.axes.grid( True )
		peaktime = self.time[ self.data.index( max( self.data ) ) ]
		self.selector = StickySpanSelector( self.axes, initial=( peaktime - 0.1, peaktime + 0.1 ), onselect=callback, granularity=0.050, units='s', fmt='%g', color='#FF6666', text_y=0.98, text_verticalalignment='top', text_visible=False )
		self.ycon = AxisController( self.axes, 'y', fmt='%g', units='V', start=self.axes.get_ylim(), narrowest=self.axes.get_ylim() ).Home()
		self.xcon = AxisController( self.axes, 'x', fmt='%g', units='s', start=self.axes.get_xlim(),    widest=self.axes.get_xlim() ).Home()
		self.xcon.focusFunction = self.selector.get
		self.Update()
	
	def Update( self, range=None ):
		if range == None: range = self.selector.get()
		if range == None: ysub = []
		else: ysub = [ y for t, y in zip( self.time, self.data ) if range[ 0 ] <= t <= range[ 1 ] ]
		if len( ysub ): 
			avg = sum( ysub ) / float( len( ysub ) )
			self.estimate = FormatWithUnits( avg, fmt='%.1f', units='V' )
			self.axes.set_title( 'Estimated MVC = ' + self.estimate )
		else:
			self.estimate = None
			self.axes.set_title( '' )

class ResponseOverlay( object ):
	def __init__( self, data, fs, lookback, channel=0, axes=None, responseInterval=( .028, .035 ), comparisonInterval=None, backgroundInterval=None, color='#0000FF', updateCommand=None, rectified=False ): 
		# return lines, span selectors, ycon, xcon
		if axes == None: axes = matplotlib.pyplot.gca()
		else: matplotlib.pyplot.figure( axes.figure.number ).sca( axes )
		self.axes = axes
		axes.grid( True )
		self.yController = AxisController( axes, 'y', units='V', start=( -0.100, +0.100 ), narrowest=( -0.0001, +0.0001 ), widest=( -20.000, +20.000 ) )
		self.xController = AxisController( axes, 'x', units='s', start=( -0.020, +0.100 ), narrowest=( -0.002,  +0.010  ), widest=( -0.100, +0.500 ) )
		if comparisonInterval == None: self.comparisonSelector = None
		else:                          self.comparisonSelector = StickySpanSelector( axes, onselect=updateCommand, initial=comparisonInterval, fmt='%g', units='s', granularity=0.0001, color='#AA5500', text_verticalalignment='bottom', text_y=1.00 )
		if backgroundInterval == None: self.backgroundSelector = None
		else:                          self.backgroundSelector = StickySpanSelector( axes, onselect=updateCommand, initial=backgroundInterval, fmt='%g', units='s', granularity=0.0001, color='#777777', text_verticalalignment='top',    text_y=0.98 )
		if responseInterval == None:   self.responseSelector   = None
		else:                          self.responseSelector   = StickySpanSelector( axes, onselect=updateCommand, initial=responseInterval,   fmt='%g', units='s', granularity=0.0001, color='#008800', text_verticalalignment='top',    text_y=0.98 )
		self.data = data
		self.channel = channel
		self.fs = fs
		self.lookback = lookback
		self.color = color
		self.lines = []
		for trial in self.data:
			values = trial[ self.channel ]
			self.lines += matplotlib.pyplot.plot( TimeBase( values, self.fs, self.lookback ), values, color=color, alpha=0.3 )
		self.yController.Home()
		self.xController.Home()
		self.Update( rectified=rectified )
		
	def Update( self, rectified=None, color=None, channel=None ):
		if rectified != None: self.rectified = rectified
		if color != None: self.color = color
		if channel != None: self.channel = channel
		for trial, line in zip( self.data, self.lines ):
			if self.rectified: line.set_ydata( [ abs( value ) for value in trial[ self.channel ] ] )
			else: line.set_ydata( trial[ self.channel ] )
			line.set_color( self.color )
		ylim = self.axes.get_ylim()
		if self.rectified: self.axes.set_ylim( [ 0, ylim[ 1 ] ] )
		else: self.axes.set_ylim( [ -ylim[ 1 ], ylim[ 1 ] ] )
			
	def ResponseMagnitudes( self, type='response', p2p=False ):
		if   type == 'response':   interval = self.responseSelector.get()
		elif type == 'comparison': interval = self.comparisonSelector.get()
		elif type == 'background': interval = self.backgroundSelector.get()
		return ResponseMagnitudes( data=self.data, channel=self.channel, interval=interval, fs=self.fs, lookback=self.lookback, p2p=p2p )

class RecruitmentCurve( object ):
	def __init__( self, overlay, axes=None, pooling=1, p2p=False, tk=False ):
		if axes == None: axes = matplotlib.pyplot.gca()
		else: matplotlib.pyplot.figure( axes.figure.number ).sca( axes )
		self.axes = axes
		self.overlay = overlay
		self.pooling = pooling
		self.p2p = p2p
		self.frame = None
		prestimColor = self.overlay.backgroundSelector.rectprops[ 'facecolor' ]
		comparisonColor = self.overlay.comparisonSelector.rectprops[ 'facecolor' ]
		responseColor = self.overlay.responseSelector.rectprops[ 'facecolor' ]
		if tk:
			widget = self.axes.figure.canvas.get_tk_widget()
			self.frame = tkinter.Frame( widget, bg=widget[ 'bg' ] )
		self.panel = Bunch(
			  bg=InfoItem( 'Mean\npre-stimulus',      0, fmt='%.1f', units='V', color=prestimColor    ).tk( self.frame, row=1 ),
			mmax=InfoItem( 'Max reference\nresponse', 0, fmt='%.1f', units='V', color=comparisonColor ).tk( self.frame, row=2 ),
			hmax=InfoItem( 'Max target\nresponse',    0, fmt='%.1f', units='V', color=responseColor   ).tk( self.frame, row=3 ),
		)
		AxesPosition( self.axes, right=0.75 )
		if self.frame:
			for row in range( 3 ): self.frame.grid_rowconfigure( row + 1, weight = 1 )
			self.frame.grid_columnconfigure( 2, weight = 1 )
			p = AxesPosition( self.axes ); rgap = 1.0 - p.right
			self.frame.place( in_=widget, relx=1.0 - rgap / 2.0, rely=1.0 - p.bottom - p.height/2, relheight=p.height*1.1, anchor='center' )
		self.Update()
					
	def Update( self, pooling=None, p2p=None ):
		if pooling != None: self.pooling = pooling
		if p2p != None: self.p2p = p2p
		def pool( x, pooling ):
			ni, n, pooled = pooling, [], []
			for start in range( 0, len( x ) - pooling + 1, pooling ):
				pooled.append( sum( x[ start : start + pooling ] ) / float( pooling ) )
				n.append( ni ); ni += pooling
			return n, pooled
		xh, h = pool( self.overlay.ResponseMagnitudes( p2p=self.p2p, type='response'   ), self.pooling )
		xm, m = pool( self.overlay.ResponseMagnitudes( p2p=self.p2p, type='comparison' ), self.pooling )
		b = self.overlay.ResponseMagnitudes( p2p=self.p2p, type='background' )
		self.n = len( b )
		
		matplotlib.pyplot.figure( self.axes.figure.number ).sca( self.axes )
		matplotlib.pyplot.cla()
		matplotlib.pyplot.plot( xh, h, linestyle='none', marker='o', markersize=10, color=self.overlay.responseSelector.rectprops[ 'facecolor' ] )
		matplotlib.pyplot.plot( xm, m, linestyle='none', marker='^', markersize=10, color=self.overlay.comparisonSelector.rectprops[ 'facecolor' ] )
		self.yController = AxisController( self.axes, 'y', units='V', fmt='%g', start=self.axes.get_ylim() )
		self.yController.ChangeAxis( start=( 0, max( self.axes.get_ylim() ) ) )
		self.axes.grid( True )
		xt = list( xh )
		while len( xt ) > 15: xt = xt[ 1::2 ]
		self.axes.set( xlim=( 0	, max( xh ) + 1 ), xticks=xt )
		self.panel.bg.set( sum( b ) / float( len( b ) ) )
		self.panel.mmax.set( max( m ) )
		self.panel.hmax.set( max( h ) )
	

class ResponseHistogram( object ):
	def __init__( self, overlay, axes=None, targetpc=66, nbins=10, p2p=False, tk=False ):
		if axes == None: axes = matplotlib.pyplot.gca()
		else: matplotlib.pyplot.figure( axes.figure.number ).sca( axes )
		self.axes = axes
		self.overlay = overlay
		self.targetpc = targetpc
		self.nbins = nbins
		self.p2p = p2p
		self.frame = None
		prestimColor = self.overlay.backgroundSelector.rectprops[ 'facecolor' ]
		comparisonColor = self.overlay.comparisonSelector.rectprops[ 'facecolor' ]
		responseColor = self.overlay.responseSelector.rectprops[ 'facecolor' ]
		if tk:
			widget = self.axes.figure.canvas.get_tk_widget()
			self.frame = tkinter.Frame( widget.master, bg=widget[ 'bg' ] )
		self.panel = Bunch(
			         n=InfoItem( 'Number\nof Trials',                  0, fmt='%g'                                     ).tk( self.frame, row=1 ),
			background=InfoItem( 'Pre-stimulus\n(Median, Mean)',       0, fmt='%.1f', units='V', color=prestimColor    ).tk( self.frame, row=2 ),
			comparison=InfoItem( 'Reference Response\n(Median, Mean)', 0, fmt='%.1f', units='V', color=comparisonColor ).tk( self.frame, row=3 ),
			  response=InfoItem( 'Target Response\n(Median, Mean)',    0, fmt='%.1f', units='V', color=responseColor   ).tk( self.frame, row=4 ),
			  uptarget=InfoItem( 'Upward\nTarget',                     0, fmt='%.1f', units='V'                        ).tk( self.frame, row=6 ),
			downtarget=InfoItem( 'Downward\nTarget',                   0, fmt='%.1f', units='V'                        ).tk( self.frame, row=7 ),
		)
		AxesPosition( self.axes, right=0.65 )
		if self.frame:
			self.entry = InfoItem( 'Target\nPercentile', self.targetpc, fmt='%g' ).tk( self.frame, row=5, entry=True )
			for row in range( 6 ): self.frame.grid_rowconfigure( row + 1, weight = 1 )
			self.frame.grid_columnconfigure( 2, weight = 1 )
			p = AxesPosition( self.axes ); rgap = 1.0 - p.right
			self.frame.place( in_=widget, relx=1.0 - rgap * 0.4, rely=1.0 - p.bottom - p.height/2, relheight=p.height*1.1, anchor='center' )
		self.Update()
					
	def Update( self, nbins=None, targetpc=None, p2p=None ):
		if nbins != None: self.nbins = nbins
		if targetpc != None: self.targetpc = targetpc
		if p2p != None: self.p2p = p2p
			
		def ResponseStats( type ):
			x = self.overlay.ResponseMagnitudes( p2p=self.p2p, type=type )
			xSorted = sorted( x )
			if len( x ) == 0: xMedian = xMean = 0.0
			else:
				xMean = sum( x ) / float( len ( x ) )
				xMedian = Quantile( xSorted, 0.5, alreadySorted=True )
			return x, xSorted, xMean, xMedian
		
		r, rSorted, rMean, rMedian = ResponseStats( 'response' )
		c, cSorted, cMean, cMedian = ResponseStats( 'comparison' )
		b, bSorted, bMean, bMedian = ResponseStats( 'background' )
		n = len( r )
		targets = Quantile( rSorted, ( self.targetpc / 100.0, 1.0 - self.targetpc / 100.0 ), alreadySorted=True )
		downtarget, uptarget = max( targets ), min( targets )
		matplotlib.pyplot.figure( self.axes.figure.number ).sca( self.axes )
		matplotlib.pyplot.cla()
		#print 'calculated = ' + repr( r )
		if len( r ): self.counts, self.binCenters, self.patches = matplotlib.pyplot.hist( r, bins=self.nbins, facecolor=self.overlay.color, edgecolor='none' )
		else: self.counts, self.binCenters, self.patches = [], [], []
		self.xController = AxisController( self.axes, 'x', units='V', fmt='%g', start=self.axes.get_xlim() )
		self.xController.Home()
		vals = [ downtarget, uptarget, rMean ]
		self.downline, self.upline, self.meanline = matplotlib.pyplot.plot( [ vals, vals ], [ [ 0 for v in vals ], [ 1 for v in vals ] ], color='#FF0000', linewidth=4, alpha=0.5, transform=self.axes.get_xaxis_transform() )
		self.panel.n.set( n )
		self.panel.background.set( [ bMedian, bMean ] )
		self.panel.comparison.set( [ cMedian, cMean ] )
		self.panel.response.set(   [ rMedian, rMean ] )
		self.panel.uptarget.set( uptarget )
		self.panel.downtarget.set( downtarget )
		

class AnalysisWindow( Dialog, TkMPL ):
	
	def __init__( self, parent, mode ):
		self.mode = mode
		self.channel = 0 # first EMG channel
		self.data = parent.data[ mode ]
		self.acceptMode = None
		TkMPL.__init__( self )
		Dialog.__init__( self, parent=parent, title='%s Analysis' % parent.modenames[ mode ], icon=os.path.join( GUIDIR, 'epocs.ico' ), geometry=parent.geometry() )
		# NB: Dialog.__init__ will not return until the dialog is destroyed
		
	def buttonbox( self ): # override default OK + cancel buttons (and <Return> key binding)
		pass
		
	def ok_down( self, event=None ): self.acceptMode = 'down'; self.ok()
	def ok_up( self, event=None ): self.acceptMode = 'up'; self.ok()
		
	def cancel( self, event=None ):
		try: self.parent.after_cancel( self.after_id )
		except: pass
		controllers = self.parent.axiscontrollers_emg1
		if hasattr( self, 'overlay' ) and self.overlay.yController in controllers: controllers.remove( self.overlay.yController )
		Dialog.cancel( self )
	
	def TimingsSaved( self ):
		result = True
		params = self.parent.operator.params
		def equal( a, b ): return float( '%g' % a ) == float( '%g' % b )
		if self.overlay.responseSelector:
			start, end = [ sec * 1000.0 for sec in self.overlay.responseSelector.get() ]
			if not equal( params._ResponseStartMsec[ 0 ], start ) or not equal( params._ResponseEndMsec[ 0 ], end ): result = False
		if self.overlay.comparisonSelector:
			start, end = [ sec * 1000.0 for sec in self.overlay.comparisonSelector.get() ]
			if not equal( params._ComparisonStartMsec[ 0 ], start ) or not equal( params._ComparisonEndMsec[ 0 ], end ): result = False
		if self.overlay.backgroundSelector:
			start, end = [ sec * 1000.0 for sec in self.overlay.backgroundSelector.get() ]
			if not equal( params._PrestimulusStartMsec[ 0 ], start ) or not equal( params._PrestimulusEndMsec[ 0 ], end ): result = False
		return result
	
	def PersistTimings( self ):
		if self.overlay.backgroundSelector:
			start, end = [ sec * 1000.0 for sec in self.overlay.backgroundSelector.get() ]
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
		params = self.parent.operator.params
		factor = self.parent.operator.GetVolts( 1 )
		if self.acceptMode == 'up':
			info = self.hist.panel.uptarget
			critical = float( info.value ) / factor
			critical = float( info.fmt % critical )
			lims = ( critical, None )
		if self.acceptMode == 'down':
			info = self.hist.panel.downtarget
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
		frame[ 'bg' ] = self.colors.bg
					
		figure, widget, container = self.NewFigure( parent=frame, prefix='an', suffix='main', width=800, height=800 )
		
		header = self.widgets.an_frame_header = tkinter.Frame( frame, bg=self.colors.header )
		footer = self.widgets.an_frame_footer = tkinter.Frame( frame, bg=self.colors.footer )
		w = self.widgets.an_button_log = tkinter.Button( footer, text='Log Results', command=self.Log ); w.pack( side='right' )
		
		if self.mode in [ 'vc' ]:
			self.mvc = MVC( self.data, fs=self.parent.fs / self.parent.sbs, callback=self.Changed )
			self.widgets.an_xadjust_mvc = PlusMinusTk( frame, controllers=self.mvc.xcon ).place( in_=widget, relx=0.92, rely=0.06, width=40, height=20, anchor='se' )
			container.pack( fill='both', expand=1 )
			
		elif self.mode in [ 'rc', 'ct', 'tt' ]:
			switch = Switch( header, title='Rectification: ', offLabel='off', onLabel='on', initialValue=0, command=self.UpdateLines )
			switch.pack( side='left', pady=3 )
			tkinter.Frame( header, bg=header[ 'bg' ] ).pack( side='left', padx=25 )
			button = self.widgets.an_button_savetimings = tkinter.Button( header, text='Use marked timings', command=self.PersistTimings )
			button.pack( side='left', pady=3 )
			if self.mode in [ 'ct', 'tt' ]:
				conditioning = tkinter.Frame( header, bg=header[ 'bg' ] )
				w = self.widgets.an_button_upcondition = tkinter.Button( conditioning, text="Up-Condition", width=10, command=self.ok_up ); w.pack( side='top', padx=5, pady=2, ipadx=16, fill='both', expand=1 )
				w = self.widgets.an_button_downcondition = tkinter.Button( conditioning, text="Down-Condition", width=10, command=self.ok_down ); w.pack( side='bottom', padx=5, pady=2, ipadx=16, fill='both', expand=1 )
				conditioning.pack( side='right' )
				
			ax1 = self.artists.an_axes_overlay = matplotlib.pyplot.subplot( 2, 1, 1 )
			responseInterval   = self.parent.operator.params._ResponseStartMsec[ self.channel ] / 1000.0, self.parent.operator.params._ResponseEndMsec[ self.channel ] / 1000.0
			comparisonInterval = self.parent.operator.params._ComparisonStartMsec[ self.channel ] / 1000.0, self.parent.operator.params._ComparisonEndMsec[ self.channel ] / 1000.0
			backgroundInterval = self.parent.operator.params._PrestimulusStartMsec[ self.channel ] / 1000.0, self.parent.operator.params._PrestimulusEndMsec[ self.channel ] / 1000.0
			#if self.mode not in [ 'rc' ]: comparisonInterval = backgroundInterval = None
			self.overlay = ResponseOverlay(
				data=self.data, channel=self.channel, 
				fs=self.parent.fs, lookback=self.parent.lookback,
				axes=ax1, color=self.colors[ 'emg%d' % ( self.channel + 1 ) ],
				responseInterval=responseInterval, comparisonInterval=comparisonInterval, backgroundInterval=backgroundInterval,
				updateCommand=self.Changed,
			)
			self.overlay.yController.set( self.parent.axiscontrollers_emg1[ -1 ].get() )
			self.parent.axiscontrollers_emg1.append( self.overlay.yController )
			self.widgets.an_yadjust_overlay = PlusMinusTk( parent=frame, controllers=self.parent.axiscontrollers_emg1 ).place( in_=widget, width=20, height=40, relx=0.93, rely=0.25, anchor='w' )
			self.widgets.an_xadjust_overlay = PlusMinusTk( parent=frame, controllers=self.overlay.xController         ).place( in_=widget, width=40, height=20, relx=0.92, rely=0.05, anchor='se' )

			ax2 = self.artists.an_axes_results = matplotlib.pyplot.subplot( 2, 1, 2 )
			
			if self.mode == 'rc':
				tkinter.Label( footer, text='Trials to pool: ', bg=footer[ 'bg' ] ).pack( side='left', padx=3, pady=3 )
				vcmd = ( self.register( self.PoolingEntry ), '%s', '%P' )
				entry = self.widgets.an_entry_pooling = tkinter.Entry( footer, width=2, validate='key', validatecommand=vcmd, textvariable=tkinter.Variable( footer, value='1' ), bg='#FFFFFF' )
				entry.pack( side='left', padx=3, pady=3 )
				switch = self.widgets.an_switch_responsemode = Switch( footer, offLabel='mean rect.', onLabel='peak-to-peak', command=self.UpdateResults )
				switch.pack( side='left', pady=3, padx=10 )
				self.recruitment = RecruitmentCurve( self.overlay, axes=ax2, pooling=1, tk=True, p2p=False )
			else:
				self.hist = ResponseHistogram( self.overlay, axes=ax2, targetpc=self.parent.operator.params._TargetPercentile, nbins=10, tk=True )
				vcmd = ( self.register( self.TargetPCEntry ), '%s', '%P' )
				self.hist.entry.widgets.value.configure( width=3, validatecommand=vcmd, validate='key' )
			
		header.grid( row=1, column=1, sticky='ns' )
		container.grid( row=2, column=1, sticky='nsew' )
		footer.grid( row=3, column=1, sticky='ns', pady=20 )
		frame.grid_rowconfigure( 2, weight=1 )
		frame.grid_columnconfigure( 1, weight=1 )
			
			
		self.UpdateResults()
		self.DrawFigures()
		self.latest = None
		self.CheckUpdate()
			
	def UpdateLines( self, rectified=False ):
		self.overlay.Update( rectified=rectified )
		self.DrawFigures()
		
	def Changed( self, *pargs ): self.latest = time.time()
	def CheckUpdate( self ): # check every 100 msec: if there is new activity, and the latest activity occurred more than 2s ago, then call autosave()
		if self.latest != None and time.time() - self.latest > 0.5: self.UpdateResults(); self.latest = None
		self.after_id = self.parent.after( 100, self.CheckUpdate )
	
	def PoolingEntry( self, oldValue, newValue ):
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
		if self.mode in [ 'vc' ]:
			self.mvc.Update()
		elif self.mode in [ 'rc' ]:
			pooling = self.widgets.an_entry_pooling.get()
			try: pooling = int( pooling )
			except: pooling = None # no change
			p2p = self.widgets.an_switch_responsemode.scale.get()
			self.recruitment.Update( pooling=pooling, p2p=p2p )
		elif self.mode in [ 'ct', 'tt' ]:
			targetpc = self.hist.entry.widgets.value.get()
			try: targetpc = float( targetpc )
			except: targetpc = None
			self.hist.Update( targetpc=targetpc )
			EnableWidget( [ self.widgets.an_button_upcondition, self.widgets.an_button_downcondition ], self.TimingsSaved() )
		if self.mode in [ 'rc', 'ct', 'tt' ]:
			if self.TimingsSaved(): self.widgets.an_button_savetimings.configure( state='disabled', bg=self.colors.button )
			else:                   self.widgets.an_button_savetimings.configure( state='normal',   bg='#FF4444' )
		ax = self.artists.get( 'an_axes_overlay', None )
		if ax: matplotlib.pyplot.figure( ax.figure.number ).sca( ax )
		self.DrawFigures()
		if 'an_button_log' in self.widgets: self.widgets.an_button_log[ 'state' ] = 'normal'
	
	def Log( self ):
		if self.mode in [ 'vc' ]:
			start, end = [ sec * 1000.0 for sec in self.mvc.selector.get() ]
			if self.mvc.estimate != None: self.parent.Log( 'MVC estimated at %s over a %g-msec window' % ( self.mvc.estimate, end - start ) )
		elif self.mode in [ 'rc' ]:
			if self.recruitment.p2p: type = 'peak-to-peak'
			else: type = 'average rectified signal'
			self.parent.Log( 'From %d measurements, pooled in groups of %d:' % ( self.recruitment.n, self.recruitment.pooling ) )
			start, end = [ sec * 1000.0 for sec in self.overlay.backgroundSelector.get() ]
			meanPrestim = self.recruitment.panel.bg.str()
			self.parent.Log( '   Mean pre-stimulus activity (%g to %g msec) = %s (%s)' % ( start, end, meanPrestim, type ) )
			start, end = [ sec * 1000.0 for sec in self.overlay.comparisonSelector.get() ]
			maxComparison = self.recruitment.panel.mmax.str()
			self.parent.Log( '   Maximum reference response (%g to %g msec) = %s (%s)' % ( start, end, maxComparison, type ) )
			start, end = [ sec * 1000.0 for sec in self.overlay.responseSelector.get() ]
			maxResponse = self.recruitment.panel.hmax.str()
			self.parent.Log( '   Maximum target response (%g to %g msec) = %s (%s)\n' % ( start, end, maxResponse, type ) )
		elif self.mode in [ 'ct', 'tt' ]:
			start, end = [ sec * 1000.0 for sec in self.overlay.responseSelector.get() ]
			self.parent.Log( 'From %s trials using target response interval from %g to %gmsec and aiming at percentile %s: ' % ( self.hist.panel.n.str(), start, end, self.hist.entry.str() ) )
			self.parent.Log( '   pre-stimulus activity (mean, median) = %s' % self.hist.panel.background.str() )
			self.parent.Log( '   reference response    (mean, median) = %s' % self.hist.panel.comparison.str() )
			self.parent.Log( '   target response       (median, mean) = %s' % self.hist.panel.response.str() )
			self.parent.Log( '   upward target = %s' % self.hist.panel.uptarget.str() )
			self.parent.Log( '   downward target = %s\n' % self.hist.panel.downtarget.str() )
			if self.mode in [ 'ct' ] and self.parent.operator.params._BaselineResponse == None:
				info = self.hist.panel.response
				baselines = self.parent.operator.params._EarlyLoggedCTBaselines
				baselines[ self.parent.operator.LastRunNumber( mode=self.mode ) ] = info.value[ 0 ]
				meanOfMedians = sum( baselines.values() ) / float( len( baselines ) )
				self.parent.Log( 'Estimated baseline so far = %s    *****\n' % info.str( meanOfMedians ) )
		self.widgets.an_button_log[ 'state' ] = 'disabled'
		
	def TargetPCEntry( self, oldValue, newValue ):
		if len( newValue ) == 0: return True
		if newValue == oldValue: return True
		try: val = float( newValue )
		except: return False
		if val < 0 or val > 100: return False
		self.Changed()
		self.parent.operator.params._TargetPercentile = val
		return True
	
class InfoItem( TkMPL ):
	def __init__( self, label, value, fmt='%s', units=None, color='#000000' ):
		TkMPL.__init__( self )
		self.label = label
		self.value = value
		self.fmt = fmt
		self.units = units
		self.color = color
	def str( self, value=None, appendUnits=True ): # do not call this  __str__ : in Python 2.5, that gives a unicode conversion error when there's a microVolt symbol in the string
		if value == None: value = self.value
		if isinstance( value, ( tuple, list ) ): return ', '.join( self.str( value=v, appendUnits=appendUnits ) for v in value )
		return FormatWithUnits( value, units=self.units, fmt=self.fmt, appendUnits=appendUnits )
	def tk( self, parent, row, entry=False ):
		if parent == None: return self
		self.widgets.label = tkinter.Label( parent, text=self.label, justify='right', bg=parent[ 'bg' ], fg=self.color )
		if entry:
			self.widgets.variable = tkinter.Variable( parent, value=self.str() )
			self.widgets.value = tkinter.Entry( parent, textvariable=self.widgets.variable, bg='#FFFFFF' )
		else:
			self.widgets.variable = None
			self.widgets.value = tkinter.Label( parent, text=self.str(), bg=parent[ 'bg' ], fg=self.color )
		self.widgets.label.grid( row=row, column=1, sticky='nse', padx=5, pady=2 )
		self.widgets.value.grid( row=row, column=2, sticky='w',   padx=5, pady=2 )
		return self
	def mpl( self, axes, y=1.0, x=1.2, **kwargs ):
		kwargs.setdefault( color=self.color )
		self.artists.label = axes.text( x=x, y=y, s=str( self.label ), transform=axes.transAxes, horizontalalignment='right', verticalalignment='center', **kwargs )
		self.artists.value = axes.text( x=x, y=y, s=' ' + self.str(),  transform=axes.transAxes, horizontalalignment='left',  verticalalignment='center', **kwargs )
		return self
	def set( self, value ):
		self.value = value
		a = self.artists.get( 'value', None )
		if a != None: self.artists.value.set_text( ' ' + self.str() )
		val = self.str()
		w = self.widgets.get( 'value', None )
		if isinstance( w, tkinter.Label ): w[ 'text' ] = val
		v = self.widgets.get( 'variable', None )
		if v != None: v.set( val )
		return self

def AxesPosition( axes, left=None, right=None, top=None, bottom=None, width=None, height=None ):
	p = axes.get_position()
	pleft, pbottom = p.get_points()[ 0 ]
	pwidth, pheight = p.size
	p = [ pleft, pbottom, pwidth, pheight ]
	if right != None and width != None: left = right - width
	if left != None: p[ 0 ] = left
	if right != None: p[ 2 ] = right - p[ 0 ]
	if width != None: p[ 2 ] = width
	if top != None and height != None: bottom =  top - height
	if bottom != None: p[ 1 ] = bottom
	if top != None: p[ 3 ] = top - p[ 1 ]
	if height != None: p[ 3 ] = height
	axes.set_position( p ) # geeeez, why'd yer have to make that so damn difficult?
	return Bunch( left=p[ 0 ], bottom=p[ 1 ], width=p[ 2 ], height=p[ 3 ], right=p[ 0 ] + p[ 2 ], top=p[ 1 ] + p[ 3 ] )

class LabelledEntry( tkinter.Frame ):
	def __init__( self, parent, label, value='', width=4, bg=None ):
		if bg == None: bg = parent[ 'bg' ]
		tkinter.Frame.__init__( self, parent, bg=bg )
		self.label = tkinter.Label( self, text=label, bg=bg, justify='right' )
		self.variable = tkinter.StringVar()
		self.entry = tkinter.Entry( self, width=width, textvariable=self.variable, bg='#FFFFFF' )
		if len( label ):
			self.label.pack( side='left', padx=3 )
			self.entry.pack( side='left', padx=3 )
		else:
			self.entry.pack( padx=3 )
		self.units = None
		self.resource = None
		self.indices = []
		self.field = None
	def get( self ): return self.variable.get()
	def set( self, value ):
		if value == None: value = ''
		elif isinstance( value, float ): value = '%g' % value
		else: value = str( value )
		self.variable.set( value )
		return self
	def connect( self, resource, firstIndex, *moreIndices, **kwargs ):  # units is the only kwarg accepted
		self.units = kwargs.pop( 'units', None )
		if len( kwargs ): raise TypeError( "connect() got an unexpected keyword argument '%s'" % kwargs.keys()[ 0 ] )
		self.resource = resource
		self.indices = [ firstIndex ] + list( moreIndices )
		self.field = firstIndex
		return self.pull()
	def pull( self ):
		value = self.resource
		for index in self.indices[ : -1 ]: value = value[ index ]
		index = self.indices[ -1 ]
		if index == '*': index = 0
		elif not isinstance( index, basestring ) and hasattr( index, '__len__' ): index = index[ 0 ]
		value = value[ index ]
		if self.units and isinstance( value, basestring ): value = value.rstrip( self.units )
		return self.set( value )
	def push( self, flags=None ):
		if flags == None: flags = {}
		changed = False
		if self.enabled:
			newValue = self.get().strip()
			if self.units: newValue += self.units
			elif newValue in [ '' ]: newValue = None
			else: newValue = float( newValue )
			destination = self.resource
			for index in self.indices[ :-1 ]: destination = destination[ index ]
			finalIndices = self.indices[ -1 ]
			if finalIndices == '*': finalIndices = range( len( destination ) )
			elif isinstance( finalIndices, basestring ) or not hasattr( finalIndices, '__len__' ): finalIndices = [ finalIndices ]
			for index in finalIndices:
				oldValue = destination[ index ]
				destination[ index ] = newValue
				if newValue != oldValue: changed = True
			if self.field not in flags: flags[ self.field ] = changed
			elif changed: flags[ self.field ] = True
		return self
	def enable( self, state ):
		if state == True: state = 'normal'
		elif state == False: state = 'disabled'
		self.label[ 'state' ] = state
		self.entry[ 'state' ] = state
		return self
	def enabled( self ): return ( self.entry[ 'state' ] != 'disabled' )
	def grid( self, *pargs, **kwargs ): tkinter.Frame.grid( self, *pargs, **kwargs ); return self
	def pack( self, *pargs, **kwargs ): tkinter.Frame.pack( self, *pargs, **kwargs ); return self
	def place( self, *pargs, **kwargs ): tkinter.Frame.place( self, *pargs, **kwargs ); return self
	
class SettingsWindow( Dialog, TkMPL ):
	
	def __init__( self, parent, mode ):
		self.mode = mode
		TkMPL.__init__( self )
		Dialog.__init__( self, parent=parent, title='Settings', icon=os.path.join( GUIDIR, 'epocs.ico' ) )
		
	def body( self, frame ):

		bg = frame[ 'bg' ]
		params = self.parent.operator.params
		units = params._VoltageUnits
		warningCommand = ( self.register( self.ValueWarnings ), '%W', '%P' )
		
		section = tkinter.LabelFrame( frame, text='Stimulus Scheduling', bg=bg )
		state = { True : 'normal', False : 'disabled' }[ self.mode in [ 'st' ] ]
		self.widgets.entry_isi_st = LabelledEntry( section, 'Min. stimulus test\ninterval (sec)').connect( params, '_SecondsBetweenStimulusTests' ).enable( state ).grid( row=1, column=1, sticky='e', padx=8, pady=8 )
		state = { True : 'normal', False : 'disabled' }[ self.mode in [ 'rc', 'ct', 'tt' ] ]
		self.widgets.entry_isi = LabelledEntry( section, 'Min. training\ninterval (sec)').connect( params, '_SecondsBetweenTriggers' ).enable( state ).grid( row=1, column=2, sticky='e', padx=8, pady=8 )
		section.pack( side='top', pady=10, padx=10, fill='both' )
		
		state = { True : 'normal', False : 'disabled' }[ self.mode in [ 'vc' ] ]
		section = tkinter.LabelFrame( frame, text='Feedback Bars', bg=bg )
		self.widgets.entry_backgroundbar = LabelledEntry( section, 'Voluntary Contraction\naxes limit (%s)\n' % units ).connect( params, '_VCBackgroundBarLimit' ).enable( state ).grid( row=1, column=1, sticky='e', padx=8, pady=8 )
		state = { True : 'normal', False : 'disabled' }[ self.mode in [ 'vc', 'rc', 'ct', 'tt' ] ]
		self.widgets.entry_refresh = LabelledEntry( section, 'Bar refresh\ncycle (msec)' ).connect( params, '_BarUpdatePeriodMsec' ).enable( state ).grid( row=2, column=1, sticky='e', padx=8, pady=8 )
		state = { True : 'normal', False : 'disabled' }[ self.mode in [ 'tt' ] ]
		w = self.widgets.entry_responsebar = LabelledEntry( section, 'Response bar\naxes limit (%s)' % units ).connect( params, '_ResponseBarLimit' ).enable( state ).grid( row=1, column=2, sticky='e', padx=8, pady=8 )
		w.entry.configure( validatecommand=warningCommand, validate='key' )
		w = self.widgets.entry_baselineresponse = LabelledEntry( section, 'Baseline\nresponse (%s)' % units ).connect( params, '_BaselineResponse' ).enable( state ).grid( row=2, column=2, sticky='e', padx=8, pady=8 )
		w.entry.configure( validatecommand=warningCommand, validate='key' )
		section.pack( side='top', pady=10, padx=10, fill='both' )

		state = { True : 'normal', False : 'disabled' }[ self.mode in [ 'rc', 'ct', 'tt' ] ]
		section = tkinter.LabelFrame( frame, text='Background EMG', bg=bg )
		subsection = tkinter.Frame( section, bg=bg )
		tkinter.Label( subsection, text='Background EMG', justify='right', state=state, bg=bg ).grid( row=1, column=1, sticky='nsw', padx=2, pady=2 )
		tkinter.Label( subsection, text='EMG 1', justify='center', state=state, bg=bg ).grid( row=1, column=2, sticky='nsew', padx=10, pady=2 )
		tkinter.Label( subsection, text='EMG 2', justify='center', state=state, bg=bg ).grid( row=1, column=3, sticky='nsew', padx=10, pady=2 )
		tkinter.Label( subsection, text='Min. (%s)' % units, justify='right',  state=state, bg=bg ).grid( row=2, column=1, sticky='nse', padx=2, pady=2 )
		tkinter.Label( subsection, text='Max. (%s)' % units, justify='right',  state=state, bg=bg ).grid( row=3, column=1, sticky='nse', padx=2, pady=2 )
		self.widgets.entry_bgmin1 = LabelledEntry( subsection, '' ).connect( params, '_BackgroundMin', 0 ).enable( state ).grid( row=2, column=2, sticky='nsew', padx=2, pady=2 )
		self.widgets.entry_bgmax1 = LabelledEntry( subsection, '' ).connect( params, '_BackgroundMax', 0 ).enable( state ).grid( row=3, column=2, sticky='nsew', padx=2, pady=2 )
		self.widgets.entry_bgmin2 = LabelledEntry( subsection, '' ).connect( params, '_BackgroundMin', 1 ).enable( state ).grid( row=2, column=3, sticky='nsew', padx=2, pady=2 )
		self.widgets.entry_bgmax2 = LabelledEntry( subsection, '' ).connect( params, '_BackgroundMax', 1 ).enable( state ).grid( row=3, column=3, sticky='nsew', padx=2, pady=2 )
		subsection.pack( fill='x', padx=10, pady=10 )
		self.widgets.entry_hold = LabelledEntry( section, 'Background hold\nduration (sec)' ).connect( params, '_BackgroundHoldSec' ).enable( state ).pack( padx=10, pady=10 )
		section.pack( side='top', pady=10, padx=10, fill='both' )

		state = { True : 'normal', False : 'disabled' }[ self.mode in [ 'tt' ] ]
		section = tkinter.LabelFrame( frame, text='Responses', bg=bg )
		subsection = tkinter.Frame( section, bg=bg )
		self.widgets.entry_rstart = LabelledEntry( subsection, 'Response interval: ' ).connect( params, '_ResponseStartMsec', '*' ).enable( state ).pack( side='left', padx=3 )
		self.widgets.entry_rend   = LabelledEntry( subsection, u'\u2013' ).connect( params, '_ResponseEndMsec', '*' ).enable( state ).pack( side='left', padx=3 )
		tkinter.Label( subsection, text=' msec', justify='left', state=state, bg=bg ).pack( side='left', padx=3 )
		subsection.pack( fill='x', padx=10, pady=10 )
		subsection = tkinter.Frame( section, bg=bg )
		tkinter.Label( subsection, text='Reward Ranges', justify='left', state=state, bg=bg ).grid( row=1, column=1, sticky='nsw', padx=2, pady=2 )
		tkinter.Label( subsection, text='EMG 1', justify='center', state=state, bg=bg ).grid( row=1, column=2, sticky='nsew', padx=10, pady=2 )
		tkinter.Label( subsection, text='EMG 2', justify='center', state=state, bg=bg ).grid( row=1, column=3, sticky='nsew', padx=10, pady=2 )
		tkinter.Label( subsection, text='Min. (%s)' % units, justify='right',  state=state, bg=bg ).grid( row=2, column=1, sticky='nse', padx=2, pady=2 )
		tkinter.Label( subsection, text='Max. (%s)' % units, justify='right',  state=state, bg=bg ).grid( row=3, column=1, sticky='nse', padx=2, pady=2 )
		self.widgets.entry_rmin1 = LabelledEntry( subsection, '' ).connect( params, '_ResponseMin', 0 ).enable( state ).grid( row=2, column=2, sticky='nsew', padx=2, pady=2 )
		self.widgets.entry_rmax1 = LabelledEntry( subsection, '' ).connect( params, '_ResponseMax', 0 ).enable( state ).grid( row=3, column=2, sticky='nsew', padx=2, pady=2 )
		self.widgets.entry_rmin2 = LabelledEntry( subsection, '' ).connect( params, '_ResponseMin', 1 ).enable( state ).grid( row=2, column=3, sticky='nsew', padx=2, pady=2 )
		self.widgets.entry_rmax2 = LabelledEntry( subsection, '' ).connect( params, '_ResponseMax', 1 ).enable( state ).grid( row=3, column=3, sticky='nsew', padx=2, pady=2 )
		subsection.pack( fill='x', padx=10, pady=10 )
		section.pack( side='top', pady=10, padx=10, fill='both' )
		self.resizable( False, False )
		w = self.widgets.label_message = tkinter.Label( frame, text='', bg=bg ); w.pack( ipadx=10, ipady=10 )
	
	
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
				if key in 'baselineresponse bgmin1 bgmin2 bgmax1 bgmax2 rmin1 rmin2 rmax1 rmax2'.split(): x = None
				else: return self.error( 'this cannot be blank', widget )
			else:
				try: x = float( x )
				except: return self.error( 'cannot interpret this as a number', widget )
				if x < 0.0: return self.error( 'this cannot be negative', widget )
				#'isi   backgroundbar refresh  responsebar baselineresponse    bgmin1 bgmax1 bgmin2 bgmax2   hold   rstart rend  rmin1 rmin2 rmax1 rmax2'
				if x == 0.0 and key in 'isi isi_st backgroundbar refresh  responsebar bgmax1 bgmax2  rmax1 rmax2'.split(): return self.error( 'this cannot be zero', widget )
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
			if not key.startswith( 'entry_' ): continue
			widget.push( changed )
		for k, v in sorted( changed.items() ):
			if v: self.parent.Log( 'Changed setting %s to %s' % ( k.strip( '_' ), repr( self.parent.operator.params[ k ] ) ) )
		if True in changed.values(): self.parent.operator.needSetConfig = True
		self.parent.SetBarLimits( 'vc', 'rc', 'ct', 'tt' )
		self.parent.SetTargets( 'vc', 'rc', 'ct', 'tt' )
		self.parent.DrawFigures()

#class SubjectChooser( Dialog, TkMPL ):
#	def __init__( self, parent ): TkMPL.__init__( self ); Dialog.__init__( self, parent=parent, title='Start Session', icon=os.path.join( GUIDIR, 'epocs.ico' ) )
#	def apply( self ): self.successful = True
#	def buttonbox( self ): self.bind( "<Escape>", self.cancel )

class SubjectChooser( tkinter.Frame ):
	
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
		self.parent.operator.LoadSettings( self.subjectVar.get(), newSession=True )
		self.ok()
		
	def ContinueSession( self ): 
		self.parent.operator.LoadSettings( self.subjectVar.get(), newSession=False )
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
if __name__ == '__main__':
	
	args = getattr( sys, 'argv', [] )[ 1: ]
	import getopt
	opts, args = getopt.getopt( args, '', [ 'log=', 'devel' ] )
	opts = dict( opts )
	log = opts.get( '--log', None )
	if log:
		log = log.replace( '###', time.strftime( '%Y%m%d-%H%M%S' ) )
		logDir = os.path.split( log )[ 0 ]
		if not os.path.isdir( logDir ): os.mkdir( logDir )
		sys.stdout = sys.stderr = open( log, 'wt', 0 )
	if '--devel' in opts: DEVEL = True
	
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
	
	self = GUI()
	#self.operator.remote.WindowVisible = 1
	if DEVEL:
		try: import pickle; self.data = Bunch( pickle.load( open( 'ExampleData.pk', 'rb' ) ) ) # TODO
		except: pass
		else: [ EnableWidget( self.MatchWidgets( mode, 'button', 'analysis' ), len( self.data[ mode ] ) ) for mode in self.data ]
	if self.ready: self.Loop()
	if log and sys.stdout.tell() == 0: sys.stdout.close(); os.remove( log )
