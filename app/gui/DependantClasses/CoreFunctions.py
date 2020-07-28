import time, os, threading, sys, glob, inspect, math

class Bunch( dict ):
	"""
	A class like a dict but in which you can de-reference members like.this as well as like['this'] .
	Used throughout.
	"""
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


def FixAspectRatio(widget, aspect_ratio=None, relx=0.5, rely=0.5, anchor='center'):
    """
    Enforce a fixed aspect ratio for a Tkinter widget.

    This is a hack (adapted from Bryan Oakley's answer to http://stackoverflow.com/questions/16523128 )
    and can only be achieved by using the .place() layout manager to place the widget in question
    (which this function does implicitly, using the specified relx, rely and anchor arguments). So if
    you wanted to .grid() or .pack() it, wrap your widget in a Tkinter.Frame and .grid() or .pack()
    that instead.
    """
    if aspect_ratio == None: aspect_ratio = float(widget['height']) / float(widget['width'])

    def EnforceAspectRatio(event):
        desired_width = event.width
        desired_height = int(0.5 + event.width * float(aspect_ratio))
        if desired_height > event.height:
            desired_height = event.height
            desired_width = int(0.5 + event.height / float(aspect_ratio))
        widget.place(relx=relx, rely=rely, anchor=anchor, width=desired_width, height=desired_height)

    widget.master.bind("<Configure>", EnforceAspectRatio)
    return widget


def EnableWidget( widget, enabled=True ):
	"""
	Place a Tkinter widget (or each one of a tuple or list of Tkinter widgets) into
	either the 'normal' or 'disabled' state according to the boolean value <enabled>.
	"""
	if isinstance( widget, ( tuple, list ) ):
		for w in widget: EnableWidget( w, enabled )
		return
	if enabled: widget.configure( state='normal' )
	else: widget.configure( state='disabled' )

#### Helper classes for graphical rendering

def Descendants( widgets ):
	"""
	On input, <widget> is either a Tkinter widget, or a tuple/list of Tkinter widgets.
	The return value is a list of widgets. It includes the input widgets, and all their
	children, and all their children's children, and so on.
	"""
	if not isinstance( widgets, ( tuple, list ) ): widgets = [ widgets ]
	widgets = list( widgets )
	for widget in tuple( widgets ):
		widgets += Descendants( widget.winfo_children() )
	return widgets

#### Very generic global functions and classes

def flush( s ):
	"""
	Like print, but without buffering: writes a string to the console, followed by a newline,
	and flushes the buffer so that it appears immediately. Used for debugging.
	"""
	sys.stdout.write( str( s ) + '\n' ); sys.stdout.flush()

def Curry( func, *creation_time_pargs, **creation_time_kwargs ):
	"""
	Return a callable object with default argument values already baked (or "curried") in. Example:

	def AddTwoNumbers( first, second ): return first + second
	PlusFive = Curry( AddTwoNumbers, second=5.0 )
	print PlusFive( 10 )
	"""
	def curried( *call_time_pargs, **call_time_kwargs ):
		pargs = creation_time_pargs + call_time_pargs
		kwargs = dict( creation_time_kwargs )
		kwargs.update( call_time_kwargs )
		return func( *pargs, **kwargs )
	curried.__doc__ = 'curried function %s(%s)' % ( func.__name__, ', '.join( [ repr( v ) for v in creation_time_pargs ] + [ '%s=%s' % ( str(k), repr(v) ) for k, v in creation_time_kwargs.items() ] ) )
	if func.__doc__: curried.__doc__ += '\n' + func.__doc__
	return curried

def GenericCallback( *pargs, **kwargs ):
	"""
	purely for development/debugging
	"""
	print pargs
	print kwargs
	return 'yeah!'

def ResolveDirectory( d, startDir=None ):
	"""
	Return an absolute path to <d>, on the assumption that <d> is either already absolute,
	or expressed relative to <startDir> (if <startDir> is not specified, it defaults to the
	current working directory).
	"""
	oldDir = os.getcwd()
	if startDir == None: startDir = oldDir
	os.chdir( startDir )
	result = os.path.abspath( d )
	os.chdir( oldDir )
	return result

def MakeWayFor( filepath ):
	"""
	Make all the necessary parent and grandparent directories to allow file <filepath> to be created.
	"""
	# we were relying on setconfig to do this for us, but a bug in BCI2000 means we cannot setconfig twice in a row without performing a run in between (if we do, the parameter values are not all updated correctly from the first to the second time)
	parent = os.path.split( filepath )[ 0 ]
	if len( parent ) and not os.path.isdir( parent ): os.makedirs( parent )
	return filepath

def ReadDict( filename ):
	"""
	Read and interpret the text representation of dict from a text file.
	"""
	if not os.path.isfile( filename ): return {}
	return eval( open( filename, 'rt' ).read() )

def WriteDict( d, filename, *fields ):
	"""
	Write a text representation of dict <d> to a text file <filename>, creating
	any necessary parent directories.  If extra arguments are supplied, limit the
	output to the named fields---i.e. whereas WriteDict(d, filename) would output
	the entire dict, WriteDict(d, filename, 'spam', 'eggs') would limit itself to
	d['spam'] and d['eggs'].
	"""
	if len( fields ): d = dict( ( k, v ) for k, v in d.items() if k in fields )
	file = open( MakeWayFor( filename ), 'wt' )
	file.write( '{\n' )
	for k, v in sorted( d.items() ): file.write( '\t%s : %s,\n' % ( repr( k ), repr( v ) ) )
	file.write( '}\n' )
	file.close()

def TryFilePath( *alternatives ):
	"""
	Work through the *alternatives, treat each one as a glob pattern specifying a file path
	(e.g. './*-spam.dat') and return the unique match to the first of them that has matches.
	If it has multiple matches, throw an error.  If no match is found to any of the
	alternatives, also throw an error.  (Specifying multiple *alternatives is a good way to
	search a path or to try to see whether a file exists with any one of a number of possible
	file extensions.)
	"""
	if len( alternatives ) == 0: return None
	for alternative in alternatives:
		results = sorted( glob.glob( alternative ) )
		if len( results ) > 1: raise IOError( 'multiple matches for "%s"' % alternative )
		if len( results ) == 1: return results[ 0 ]
	raise IOError( 'could not find a match for "%s"' % alternatives[ 0 ] )

DB_ON = False
DB_LOCK = threading.Lock()
def DB( *pargs, **kwargs ):
	"""
	Call DB('on') to enable debug logging, and DB('off') to disable it.
	In between, any call to DB() will write a date-stamped and line-number-stamped line
	to sys.stderr,  together with any optional pargs and kwargs,  e.g.:
	DB( 'hello', spam=5, eggs='EGGS' ) # might write:
	2014-06-23  13:23:33  line  154  hello,  eggs='EGGS',  spam=5
	"""
	global DB_ON, DB_LOCK
	if len( pargs ) and isinstance( pargs[ 0 ], ( bool, basestring ) ) and pargs[ 0 ] in [ True,  'ON',  'on'  ]: DB_ON = True
	if not DB_ON: return
	stamp = time.strftime( '%Y-%m-%d  %H:%M:%S', time.localtime() )
	argstr = ',  '.join( [ str( x ) for x in pargs ] + [ '%s=%s' % ( key, repr( value ) ) for key, value in sorted( kwargs.items() ) ] )
	caller = inspect.stack()[ 1 ]
	info = inspect.getframeinfo( caller[ 0 ] )
	DB_LOCK.acquire()
	file = sys.stderr
	file.write( '%s  line %4d (%s)  %s\n' % ( stamp, info.lineno, info.function, argstr ) )
	file.flush()
	if len( pargs ) and isinstance( pargs[ 0 ], ( bool, basestring ) ) and pargs[ 0 ] in [ False, 'OFF', 'off' ]: DB_ON = False
	DB_LOCK.release()


#### Very general global functions for dealing with signals

def GetVolts( value, units ):
	"""
	Assuming <value> is expressed in <units> (which might be 'V', 'mV', 'uV' or 'muV'), return the
	corresponding value unequivocally in Volts.  You can also process a whole sequence (tuple or list)
	of values this way.  Usually not called directly, but rather via the Operator.GetVolts() method.
	"""
	if isinstance( value, ( tuple, list ) ): return value.__class__( GetVolts( x, units ) for x in value )
	if value == None: return None
	factors = { '' : 1e0, 'v' : 1e0, 'mv' : 1e-3, 'muv' : 1e-6, 'uv' : 1e-6 }
	return value * factors[ units.lower() ]

def FormatWithUnits( value, context=None, units='', fmt='%+g', stripZeroSign=True, appendUnits=True ):
	"""
	Let's say your <value> is expressed in uninflected <units> ('V' for Volts or 's' for seconds)
	and you want a string representation of that value in the most convenient form of those units
	(nano-, micro-, or milli- units, or just plain units).  This function formats such a string,
	appending the inflected units string itself unless you explicitly say appendUnits=False.  The
	decision about whether to go nano, micro, or milli is taken according to the magnitude of
	<value> itself, unless you supply a list of values in <context>:  in the latter case, the
	maximum absolute value in <context> is used to set the scale.  For example, you might want
	to call FormatWithUnits once for each tick label on an axis, but with <context> equal to the
	full set of tick values each time so that they are all scaled the same.

	Used in multiple graphical rendering routines throughout the GUI, SettingsWindow and AnalysisWindow.
	"""
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
	"""
	Given a sequence of voltage <values> that make up an epoch, return a list of time
	values (in seconds) against which to plot them, on the assumption that <fs> samples
	are recorded per second and that the epoch starts <lookback> seconds before
	nominal time 0.

	Used in graphical rendering routines throughout the GUI, SettingsWindow and AnalysisWindow.
	"""
	return [ float( sample ) / fs - lookback for sample, value in enumerate( values ) ]

class Monitor(object):
    x = 0
    y = 0
    width = 0
    height = 0

    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def __repr__(self):
        return 'monitor(%dx%d+%d+%d)' % (
            self.width, self.height, self.x, self.y)

class MonitorEnumeratorWindows(object):
    @staticmethod
    def detect():
        return 'win32' in sys.platform

    @staticmethod
    def get_monitors():
        import ctypes
        import ctypes.wintypes
        monitors = []

        def callback(monitor, dc, rect, data):
            rct = rect.contents
            monitors.append(Monitor(
                rct.left,
                rct.top,
                rct.right - rct.left,
                rct.bottom - rct.top))
            return 1

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.wintypes.RECT),
            ctypes.c_double)

        ctypes.windll.user32.EnumDisplayMonitors(
            0, 0, MonitorEnumProc(callback), 0)

	return monitors

def get_monitors():
	enumerators = [MonitorEnumeratorWindows]
	chosen = None
	for e in enumerators:
		if e.detect():
			chosen = e
	if chosen is None: raise NotImplementedError('This environment is not supported.')
	return chosen.get_monitors()

def ResponseMagnitudes( data, channel, interval, fs, lookback, p2p=False, SingleTrial=False):
	"""
	Global helper function called by ResponseOverlay.ResponseMagnitudes():
	assuming each data[ trialIndex ][ channelIndex ][ sampleIndex ] is a floating-point
	number, and given a tuple specifying the endpoints of the <interval> of interest in
	seconds, as well as the sampling frequency <fs> in Hz and the <lookback> in seconds,
	return a list of response magnitudes, one per trial, for the specified <channel>.
	If p2p=True, these are peak-to-peak values in the interval of interest. If not, they
	are mean rectified values across the interval of interest.
	"""
	interval = min( interval ), max( interval )
	start, length = interval[0], interval[1] - interval[0]
	start = round((start + lookback) * fs) + 1
	length = round(length * fs)
	if not SingleTrial:
		r = []
		for trial in data:
			y = trial[ channel ]
			y = [ yi for i, yi in enumerate( y ) if start <= i < start + length ]
			if p2p: r.append( max( y ) - min( y ) )
			else: r.append( sum( abs( yi ) for yi in y ) / float( len( y ) ) )
		return r
	else:
		y = data[channel]
		y = [yi for i, yi in enumerate(y) if start <= i < start + length]
		if p2p: return (max(y) - min(y))
		else: return (sum(abs(yi) for yi in y) / float(len(y)))

def Quantile( x, q, alreadySorted=False ):
	"""
	Global helper function called by ResponseDistribution.Update()
	Given a list of floating-point values <x>, which may or may not already be sorted
	in ascending order (pass alreadySorted=True if they are, to save computational effort),
	return the q'th quantile of the values. If q is out of range (e.g. q=0, q=1, or too
	close to 0 or 1 given the number of samples in x) then min(x) or max(x) is returned.

	q may be a scalar floating-point quantile specifier ( 0 <= q <= 1 ) or it may be
	a tuple/list of quantile specifiers: in the latter case, a list of values is returned.
	"""
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

def AxesPosition( axes, left=None, right=None, top=None, bottom=None, width=None, height=None ):
	"""
	A global function for getting and/or setting all the position information about a
	matplotlib.pyplot.axes object.  There should/must surely be an easier way of doing
	this but I couldn't find it.  Used by the ResponseSequence and ResponseDistribution
	classes.
	"""
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
