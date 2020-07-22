import Tkinter as tkinter
from CoreFunctions import *
import math, matplotlib, ttk, re
from TK import TkMPL
import numpy

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

class OptionsDialog(tkinter.Toplevel):
    """
    A simple options dialog with two options
    """

    def __init__(self,title='H-Reflex Stimulus Test',option1='Stop',option2='Continue >>',returnVals=(0,1)):

        tkinter.Toplevel.__init__(self)
        self.wm_title(title)
        self.wm_resizable(width=False, height=False)

        self.returnVals = returnVals
        self.Options = [option1, option2]
        self.Button = 1

        self.CreateWindow()

    def CreateWindow(self,header=None):
        """
        Creates the main GUI interface
        """

        #This should really embed into the Stimulation Control Panel if it exists
        if header == None: header = tkinter.Frame(self)

        self.Label = w = tkinter.Label(header,text='Break! Press continue when ready...', padx=3, pady=3,font=6)
        w.pack(side='top')#grid(row=0, column=0, columnspan=4, padx=1, pady=1, sticky='ew')

        b = []
        for i in range(2):
            b.append(tkinter.Button(header, text=self.Options[i], command= lambda x=i: self.Close(val=x),font=6,borderwidth=2))
            if i == 0: b[i]['fg'] = 'red4'
            else: b[i]['fg'] = 'dark green'

        b[1].pack(side='right',padx=3,pady=1)
        b[0].pack(side='right', padx=3, pady=1)

        header.pack(side='top', fill='both', expand=1)

    def Close(self,val):
        self.Button = val
        self.destroy()

    def GetValuePressed(self):
        """
        Returns what button was pressed
        """
        #self.wm_deiconify()
        self.wait_window()
        return self.Button

class ConnectedWidget( tkinter.Frame ):
	"""
	A Tkinter widget (derived from Frame) with a few extra powers:
		- .connect( resource, field, [indices...] ) allows the widget to .push() and .pull() its value
		  to and from a particular resource (which could for example be a dict)
		- .enable( True ) and .enable( False ) allow enabling/disabling of
		  the widget and all its subwidgets, and .enabled() will query this state.
		- .grid(), .pack() and .place() return self (cutting down on the number of lines you need to write)
	"""
	def __init__( self, parent, bg=None ):
		"""
		<parent>: the Tkinter master widget
		<bg>: the background color
		"""
		if bg is None: bg = parent[ 'bg' ]
		tkinter.Frame.__init__( self, parent, bg=bg )
		self.resource = None
		self.indices = []
		self.field = None
		self.variable = tkinter.StringVar()
		self.__enabled = True
	def get( self ):
		"""
		Return the value of the widget's underlying variable, as a string.
		"""
		return self.variable.get()
	def set( self, value ):
		"""
		Set the value of the widget's underlying string variable.
		"""
		if value == None: value = ''
		elif isinstance( value, float ): value = '%g' % value
		else: value = str( value )
		self.variable.set( value )
		return self
	def connect( self, resource, firstIndex, *moreIndices, **kwargs ):  # units is the only kwarg accepted
		"""
		Create an (optional) association between this widget and a place in memory,
		<resource>, where the widget's value may be stored.

		Examples:
			widget.connect( resource, fieldName ):
				widget.pull()  will do   widget.set( resource[fieldName] )
				widget.push()  will do   resource[fieldName] = widget.get()  plus or minus a few subtleties
			widget.connect( resource, fieldName, i, j, k ):
				widget.pull()  will do   widget.set( resource[fieldName][i][j][k] )
				widget.push()  will do   resource[fieldName][i][j][k] = widget.get()  plus or minus a few subtleties

		One of the subtleties is that a <units> keyword may be specified when calling connect().
		"""
		self.units = kwargs.pop( 'units', None )
		if len( kwargs ): raise TypeError( "connect() got an unexpected keyword argument '%s'" % kwargs.keys()[ 0 ] )
		self.resource = resource
		self.indices = [ firstIndex ] + list( moreIndices )
		self.field = firstIndex
		return self.pull()
	def pull( self ):
		"""
		Assuming you have configured the widget with .connect(),  pull the value of the
		widget from the configured resource.
		"""
		value = self.resource
		for index in self.indices[ : -1 ]: value = value[ index ]
		index = self.indices[ -1 ]
		if index == '*': index = 0
		elif not isinstance( index, basestring ) and hasattr( index, '__len__' ): index = index[ 0 ]
		value = value[ index ]
		if isinstance( value, basestring ) and self.units and value.rstrip().endswith( self.units ):
			value = value.rstrip()[ -len( self.units ): ].rstrip()
		return self.set( value )
	def push( self, flags=None ):
		"""
		Assuming you have configured the widget with .connect(),  push the value of the
		widget to the configured resource.  The optional argument <flags> may be a dict
		or Bunch object.  If supplied, flags[x] is set to True or False to indicate
		whether the value has changed since the last push(),  where <x> is the first
		index (usually a field name) configured during connect().
		"""
		if flags == None: flags = {}
		changed = False
		if self.enabled():
			tempValue = self.get()
			if isinstance(tempValue,str): newValue = self.get().strip()
			else: newValue = tempValue
			if self.units: newValue += self.units
			elif newValue in [ '' ]: newValue = None
			else:
				try: newValue = float( newValue )
				except: pass
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
		"""
		<state> is True or False
		Enable or disable (gray out) the widget and its subwidgets.
		"""
		self.__enabled = state
		if state and state != 'disabled': state = 'normal'
		else: state = 'disabled'

		for widget in Descendants( self ):
			if 'state' in widget.config():
				widget[ 'state' ] = state
		return self
	def enabled( self ): return self.__enabled
	def grid( self, *pargs, **kwargs ): tkinter.Frame.grid( self, *pargs, **kwargs ); return self
	def pack( self, *pargs, **kwargs ): tkinter.Frame.pack( self, *pargs, **kwargs ); return self
	def place( self, *pargs, **kwargs ): tkinter.Frame.place( self, *pargs, **kwargs ); return self

class Switch( ConnectedWidget ):
	"""
	This ConnectedWidget subclass is a compound widget that presents itself as
	a sliding single-pole-double-throw switch. Its value, queried using get() or
	changed programmatically using set(), can be either 0 or 1.
	"""
	def __init__( self, parent, title='', offLabel='off', onLabel='on', initialValue=0, command=None, values=( False, True ), bg=None, **kwargs ):
		"""
		<parent> is the parent Tkinter widget.
		<command> is the callback function to be called whenever the switch is switched
		<values> specifies the possible input arguments to <command>:  the callback will
		be called with a single argument, which will be either values[0] or values[1]
		depending on whether the switch has just been turned off or on.
		"""
		if bg == None: bg = parent[ 'bg' ]
		ConnectedWidget.__init__( self, parent, bg=bg )
		self.title = tkinter.Label( self, text=title, justify='right', bg=bg )
		self.title.pack( side='left', fill='y', expand=True )
		self.offLabel = tkinter.Label( self, text=offLabel, justify='right', bg=bg )
		self.offLabel.pack( side='left', fill='y', expand=True )
		length = kwargs.pop('length', 50); sliderlength = kwargs.pop('sliderlength', 20)
		self.scale = tkinter.Scale( self, showvalue=0, orient='horizontal', from_=0, to=1, length=length, sliderlength=sliderlength, command=self.switched )
		self.scale.configure( troughcolor=bg, borderwidth=1 )
		if len( kwargs ): self.scale.configure( **kwargs )
		self.scale.pack( side='left' )
		self.onLabel = tkinter.Label( self, text=onLabel, justify='left', bg=bg )
		self.onLabel.pack( side='right', fill='y', expand=True )
		self.command = command
		self.values = values
		self.set( initialValue )
	def get( self, as_bool=False ):
		value = self.scale.get()
		if not as_bool: value = self.values[ value ]
		return value
	def set( self, value, as_bool=False ):
		if not as_bool: value = self.values.index( value )
		self.scale.set( value )
		return self
	def switched( self, arg=None ):
		"""
		Callback for internal use.  Calls whichever callback was set by the
		<command> parameter to the object constructor, as well as updating
		the appearance of the switch.
		"""
		colors = '#000000', '#888888'
		state = self.get( as_bool=True )
		if state: colors = colors[ ::-1 ]
		self.offLabel[ 'fg' ], self.onLabel[ 'fg' ] = colors
		state = self.values[ state ]
		self.variable.set( str( state ) )
		if self.command: self.command( state )

class Switch3(ConnectedWidget):
	"""
	This ConnectedWidget subclass is a compound widget that presents itself as
	a sliding single-pole-double-throw switch. Its value, queried using get() or
	changed programmatically using set(), can be either 0 or 1.
	"""
	def __init__( self,parent,title='', labels = ('','',''), initialValue=0, command=None, values=( 0,1,2 ), bg=None, **kwargs ):
		"""
		<parent> is the parent Tkinter widget.
		<command> is the callback function to be called whenever the switch is switched
		<values> specifies the possible input arguments to <command>:  the callback will
		be called with a single argument, which will be either values[0] or values[1]
		depending on whether the switch has just been turned off or on.
		"""
		if bg == None: bg = parent[ 'bg' ]
		ConnectedWidget.__init__( self, parent, bg=bg )
		self.title = tkinter.Label(self, text=title, justify='right', bg=bg)
		self.title.pack(side='left', fill='y', expand=True)

		idx = labels.index(initialValue)
		self.Label = tkinter.Label(self, text=labels[idx], justify='left', bg=bg,width=6)
		self.Label.pack(side='right', fill='y', expand=True)
		self.Labels=labels

		self.scale = tkinter.Scale( self, showvalue=0, orient='horizontal', from_=0, to=2, length=75, sliderlength=20, command=self.switched )
		self.scale.configure( troughcolor=bg, borderwidth=1 )
		if len( kwargs ): self.scale.configure( **kwargs )
		self.scale.pack( side='left' )

		self.command = command
		self.values = values
		self.set( initialValue )

	def get( self, as_bool=False ):
		value = self.scale.get()
		if not as_bool: value = self.values[ value ]
		return value
	def set( self, value, as_bool=False ):
		if not as_bool: value = self.values.index( value )
		self.scale.set( value )
		return self
	def switched( self, arg=None ):
		"""
		Callback for internal use.  Calls whichever callback was set by the
		<command> parameter to the object constructor, as well as updating
		the appearance of the switch.
		"""
		#colors = '#000000', '#888888'
		#state = self.get( as_bool=True )
		#if state: colors = colors[ ::-1 ]
		#self.Label[ 'fg' ], self.Label[ 'fg' ] = colors
		state = self.get()
		self.Label['text'] = state #self.Labels[state]
		#state = self.values[ state ]
		self.variable.set( str( state ) )
		if self.command: self.command( state )

class AxisController( object ):
	"""
	A helper class for controlling the scaling and managing the tick labels on
	the horizontal (axisname='x') or vertical (axisname='y') axis of the specified
	matplotlib <axes> instance.

	You can specify two-element tuples to specify the <narrowest> and <widest>
	allowable limits, and also where to <start>.   You can also specify the
	<units> (e.g. 'V' for Volts or 's' for seconds) if you want the tick labels
	to be intelligently labelled according to the order-of-magnitude of the
	scaling using FormatWithUnits().

	Use the set() method to change the limits, or ChangeAxis( -1 ) and ChangeAxis( +1 )
	to zoom in and out by a pretty-printable amount.

	By default, the origin of expansion/contraction for zooming is 0.  The only place
	where 0 isn't appropriate is in the VC AnalysisWindow:  then the .focusFunction
	of the AxisController object is set manually to a function that return a tuple
	specifying the region-of-interest (the get() method of a StickSpanSelector instance,
	in fact) and this provides a crude way of allowing the origin to change.
	"""
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
		"""
		Redraw the associated figure.  Called for example by PlusMinus.Draw()
		"""
		self.axes.figure.canvas.draw()

	def FormatTicks( self, value, index ):
		"""
		Function for formatting the tick labels according to FormatWithUnits. Not called directly, but
		gets registered with the matplotlib API via matplotlib.pyplot.axes.set_major_formatter
		"""
		fudge = 0.001 * ( max( self.lims ) - min( self.lims ) )
		locs = [ x for x in self.axis.get_majorticklocs() if min( self.lims ) - fudge <= x <= max( self.lims ) + fudge ]
		appendUnits = value >= max( locs ) * ( 1 - 1e-8 ) # allow a small tolerance, again to account for precision errors
		return FormatWithUnits( value=value, context=locs, units=self.units, fmt=self.fmt, appendUnits=appendUnits )

	def get( self ):
		"""
		Return the current axes limits.
		"""
		if   self.axisname == 'x': lims = self.axes.get_xlim()
		elif self.axisname == 'y': lims = self.axes.get_ylim()
		return lims

	def set( self, lims ):
		"""
		Change the axes limits to the tuple specified by <lims>.
		Note: does not call DrawAxes() automatically.
		"""
		return self.ChangeAxis( direction=0.0, start=lims )

	def ChangeAxis( self, direction=0.0, start=None ):
		"""
		Widen (direction=+1), narrow (direction=-1), or set
		(direction=0, start=some tuple) the axes limits. Acts
		as the underlyng implementation for set() and Home()
		and is also called by PlusMinus.ChangeAxis()

		Note: does not call DrawAxes() automatically.
		"""
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
		if self.widest != None:
			lims[ 0 ] = max( min( self.widest ), lims[ 0 ] )
			lims[ 1 ] = min( max( self.widest ), lims[ 1 ] )

		self.canZoomIn  = ( self.narrowest == None or lims[ 0 ] < min( self.narrowest ) or lims[ 1 ] > max( self.narrowest ) or self.focusFunction != None )
		self.canZoomOut = ( self.widest    == None or lims[ 0 ] > min( self.widest    ) or lims[ 1 ] < max( self.widest    ) )
		self.lims = tuple( lims )
		if   self.axisname == 'x': self.axes.set_xlim( lims )
		elif self.axisname == 'y': self.axes.set_ylim( lims )
		return self

	def Home( self ):
		"""
		Go back to the limits that the AxisController had when created (self.start).
		Note: does not call DrawAxes() automatically.
		"""
		return self.ChangeAxis( direction=0.0, start=self.start )

	def ChangeValue( self, value, direction ):
		"""
		Stateless helper function for ChangesAxis().  Returns the next largest (direction=-1)
		or next smallest (direction=-1) pretty-printable value relative to <value>.
		"""
		def rnd( x ): return float( '%.8g' % x ) # crude but effective way of getting rid of nasty numerical precision errors
		x = 10.0 ** round( math.log10( value ) )
		#vals = [ x*0.1, x*0.2, x*0.5, x*1.0, x*2.0, x*5.0, x*10.0 ]
		vals = [ x*0.1 , x*0.15, x*0.2 ,x*0.3, x*0.6, x*1,x*2,x*4,x*6,x*8,x*10]
		if   direction > 0.0: value = min( x for x in vals if rnd( x ) > rnd( value ) )
		elif direction < 0.0: value = max( x for x in vals if rnd( x ) < rnd( value ) )
		return rnd( value )

class DetermineRCPoint(tkinter.Toplevel):

	def __init__(self, parent, ntrials, data, channel):

		tkinter.Toplevel.__init__(self)

		self.parent = parent
		self.ntrials = ntrials
		self.OptionValue = '1'
		self.wm_title('Choose Trial')
		self.data = data
		self.channel = channel

		w = 520
		h = 120

		if len(get_monitors())>1:
			x = self.parent.winfo_x() + self.parent.winfo_screenwidth() / 3
			y = self.parent.winfo_screenheight() / 5
		else:
			x = self.parent.winfo_screenwidth() / 3
			y = self.parent.winfo_screenheight() / 5
		self.geometry = self.geometry('%dx%d+%d+%d' % (w, h, x, y))

		self.protocol('WM_DELETE_WINDOW',self.Continue)

		self.body()
		self.wait_window()

	def buttonbox( self ): # override default OK + cancel buttons (and <Return> key binding)
		"""
		No standard OK/cancel buttons.
		"""
		pass

	def Continue( self ):

		#Either average the ntrials of data or take the single trial and pass it back to the MwaveAnalysis Window
		self.Avg = []

		try:
			i = int(self.menuVar.get())
			if self.switch.get():

				N = int(self.TrialsPool.get())
				R = range((i-1)*N,(N*i))

				y = []
				for i, x in enumerate(R): y.append(self.data[x][self.channel])
				self.Avg = [sum(col)/float(len(col)) for col in zip(*y)]
			else:
				self.Avg = self.data[i][self.channel]
		except: pass
		self.destroy()

	def body(self):

		font = ('Helvetica', 15)

		header = tkinter.Frame(self)

		self.labeltxt = tkinter.StringVar()
		self.label = tkinter.Label(header, font=font, textvariable=self.labeltxt)
		self.labeltxt.set("Choose which Trial to use:")
		self.label.grid(row=0, column=0,columnspan=2,padx=10,pady=5,sticky='w')

		self.menuTitle = '(Trials)'
		self.menuVar = tkinter.StringVar(header)
		self.OptionsList = [str(x) for x in range(1, self.ntrials + 1)]
		self.menu = w = tkinter.OptionMenu(header, self.menuVar, *self.OptionsList,command=self.SelectFromMenu)
		self.menuVar.set('--')
		self.menuVar.trace('w', self.SelectFromMenu)
		w.configure(width=5, font=font)
		w.grid(row=0, column=2,padx=10,pady=5,sticky='w')

		self.continueButton = tkinter.Button(header, text='Continue >>', command=self.Continue, font=font,state='disabled')
		self.continueButton.grid(row=0, column=3,padx=10,pady=5,sticky='w')

		self.switch = Switch(header, title='', offLabel='Trials', onLabel='Currents', initialValue=0,
						command=self.TrialvsCurrent)
		self.switch.grid(row=2,column=0,columnspan=2,padx=10,pady=5,sticky='w')

		label2 = tkinter.Label(header,text= "Trials/pool:")
		label2.grid(row=3,column=0,padx=10,pady=5,sticky='w')

		self.TrialsPool = tkinter.StringVar()
		self.entry = tkinter.Entry(header,textvariable=self.TrialsPool,width=5,bg='white')
		self.entry.grid(row=3, column=1,padx=10,pady=5,sticky='w')
		self.entry.config(state="disabled")
		self.TrialsPool.trace("w",self.ChangeValue)

		header.pack(side='top', fill='both', expand=1)


	def ChangeValue(self,x=0,y=0,z=0):

		v = self.ValidateEntry(value=self.TrialsPool.get())
		if v != False: self.TrialvsCurrent(value=1)

	def ValidateEntry(self,value):
		try:
			if value:
				v = int(value)
				self.entry.config(bg='green')
				return v
			else: return False
		except:
			self.entry.config(bg='red')
			return False

	def TrialvsCurrent(self,value):

		if value == 0:
			self.menu["menu"].delete(0,"end")
			self.OptionsList = [str(x) for x in range(1, self.ntrials + 1)]
			for x in self.OptionsList: self.menu["menu"].add_command(label=x,command=lambda temp = x: self.menuVar.set(temp))
			self.labeltxt.set("Choose which Trial to use:")
			self.continueButton['state'] = 'disabled'
			self.entry.config(state="disabled")
		else:
			self.entry.config(state="normal")
			if self.ValidateEntry(value=self.TrialsPool.get()) != False:
				N = self.ValidateEntry(value=self.TrialsPool.get())
				self.menu.children["menu"].delete(0, "end")
				self.OptionsList = [str(x) for x in range(1,((self.ntrials)/N)+1)]
				for x in self.OptionsList: self.menu["menu"].add_command(label=x,command=lambda temp=x: self.menuVar.set(temp))
				self.menuVar.set('--')
				self.labeltxt.set("Choose which Current to use:")
				self.continueButton['state'] = 'disabled'
		return False

	def SelectFromMenu(self,value=0,extra=0,extra2=0):
		try:
			int(self.menuVar.get())
			self.OptionValue = int(self.menuVar.get())
			if self.OptionValue != self.menuTitle:
				self.continueButton['state'] = 'normal'
		except:
			return None

class PlusMinus( object ):
	"""
	This is the superclass of PlusMinusMPL and PlusMinusTk.  It is an abstract representation
	of the compound graphical widget consisting of adjacent "-" (zoom out) and "+" (zoom in)
	buttons and it links these to one or more AxisController() instances.
	"""
	def __init__( self, controllers, orientation=None ):
		"""
		<controllers> is an AxisController() instance or a list of such instances.
		<orientation> may be 'vertical' or 'horizontal'  (for which 'y' and 'x', respectively,
		are synonyms). If left blank (equal to None), orientation will be inferred from the
		AxisController objects.
		"""
		if not isinstance( controllers, ( tuple, list ) ): controllers = [ controllers ]
		self.controllers = controllers
		if orientation == None: orientation = self.controllers[ 0 ].axisname
		if   orientation.lower() in [ 'y', 'vertical' ]:   self.orientation = 'vertical'
		elif orientation.lower() in [ 'x', 'horizontal' ]: self.orientation = 'horizontal'
		else: raise ValueError( 'unrecognized orientation="%s"' % orientation )
	def ChangeAxis( self, event=None, direction=+1 ):
		"""
		This method, possibly with a specific <direction> baked into it using Curry(), will be
		used as the button callback for the underlying Tkinter or matplotlib button object.
		It calls the AxisController.ChangeAxis() method of each of the associated AxisController
		instances, then calls Draw() to update the display.

		Additionally, this method may take an optional input argument, which will presumably
		be some kind of event instance when the Tkinter (and possibly matplotlib?) framework
		calls it.  The information in the event instance is ignored, but if supplied, the
		instance will be used internally to prevent the same event from being handled twice.
		"""
		if event != None:
			if getattr( event, 'AlreadyHandled', None ) != None: return # don't know why this should be necessary, or how to avoid it in some better way, but hey, this works
			event.AlreadyHandled = 1
		for c in self.controllers: c.ChangeAxis( direction )
		self.Draw()
		return self
	def Enable( self, button, value ):
		"""
		The subclass (PlusMinusMPL or PlusMinusTk) must overshadow this.
		<button> will be either self.plusButton or self.minusButton, a Tkinter or matplotlib
		object representing one of the two buttons.  <value> will be either True (enabled)
		or False (disabled).
		"""
		raise TypeError( 'cannot use the %s superclass - use a subclass instead' % self.__class__.__name__ )
	def Draw( self ):
		"""
		Call the subclass Enable() method according to whether the buttons should be enabled or
		disabled, then call AxisController.DrawAxes() for each of the AxisController instances,
		to update the display.
		"""
		plusEnabled = minusEnabled = False
		for c in self.controllers:
			if c.canZoomOut: minusEnabled = True
			if c.canZoomIn:   plusEnabled = True
		self.Enable( self.plusButton, plusEnabled )
		self.Enable( self.minusButton, minusEnabled )
		for c in self.controllers: c.DrawAxes()

class PlusMinusMPL( PlusMinus ):
	"""
	A PlusMinus() subclass that implements zoom buttons using matplotlib buttons.
	This was used in initial development of EPOCS but was then supplanted by the
	PlusMinusTk() class.
	"""
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
	"""
	A PlusMinus() subclass that implements zoom buttons using the Tkinter toolkit.
	It presents itself (actually duck-types itself) as a compound Tkinter widget
	by implementing grid(), pack() and place() methods.
	"""
	def __init__( self, parent, controllers, orientation=None ):
		"""
		<parent> is the parent Tkinter widget.  For the rest, see the PlusMinus()
		superclass documentation.
		"""
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
	def place_forget(self, *pargs, **kwargs):	self.frame.place_forget(*pargs, **kwargs); return self
	def Enable( self, button, state ):
		"""
		<button> will be either self.plusButton or self.minusButton, a Tkinter or matplotlib
		object representing one of the two buttons.  <value> will be either True (enabled)
		or False (disabled). Called by the superclass PlusMinus.Draw() method.
		"""
		EnableWidget( button, state )

class StickySpanSelector( object ): # definition copied and tweaked from matplotlib.widgets.SpanSelector in matplotlib version 0.99.0
	"""
	A novel matplotlib widget loosely based on matplotlib.widgets.SpanSelector
	The main difference is that the StickySpanSelector is visible all the time.
	Its edges can be adjusted by clicking near them and dragging, or by using
	the arrow keys (press the enter key to toggle between edges, and between
	StickySpanSelectors if there's more than one on the axes).
	"""
	def __init__( self, ax, onselect=None, initial=None, direction='horizontal', fmt='%+g', units='', minspan=None, granularity=None, useblit=False, **props ):
		"""
		<ax> is the matplotlib.pyplot.axes instance on which the widget will be drawn

		<onselect> is the callback called whenever the span changes (the callback
		should take the upper and lower values of the span as two separate arguments).

		<initial> can be None (in which case the selector does not appear until the
		user clicks for the first time) or it can specify the initial range over which
		to draw the selector.

		<direction> may be 'horizontal' (the default) or 'vertical'.

		<fmt> and <units> are passed onto FormatWithUnits to pretty-print the numeric
		values of the span limits at the top of the selector.

		<minspan> is a scalar value specifying the minimum allowable width of the selector.

		<granularity> specifies the base to which span endpoints are rounded.

		<useblit> can remain equal to False (its implementation was copied from
		matplotlib.widgets.SpanSelector but I'm not sure what it is for - it hasn't ever
		proved necessary).

		Additional keyword arguments may specify color, etc and are applied to both the
		matplotlib.patches.Rectangle that forms the main body of the rendered selector, and
		the text objects that render the numerical limit values. To restrict to one or the
		other, prepend rect_ or text_ to the keyword (e.g.  text_color='#000000')
		text_y  and text_verticalalignment are useful for changing the position of the text
		labels so that the labels from multiple selectors do not clash.  text_visible=False
		is an easy way to get rid of the labels.
		"""
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
		"""
		Return a list of pointers to other StickySpanSelectors that go in
		the same direction on the same axes as self.
		"""
		attr = self.direction + 'StickySpanSelectors'
		if not hasattr( self.ax, attr ): setattr( self.ax, attr, [] )
		return getattr( self.ax, attr )

	def new_axes( self, ax ):
		"""
		Helper function for creating the actual matplotlib artists and
		performing one-time setup of the mouse and keyboard callbacks.
		Called during construction of the instance.
		"""
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
		"""
		matplotlib key-press callback, registered during new_axes() using the matplotlib canvas's mpl_connect() method
		"""
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
		"""
		Return the current span, as a two-element tuple.
		"""
		if self.direction == 'horizontal':
			start = self.rect.get_x()
			extent = self.rect.get_width()
		else:
			start = self.rect.get_y()
			extent = self.rect.get_height()
		return ( start, start + extent )

	def set( self, span, trigger_callback=True ):
		"""
		Set the <span> as a two-element tuple or list.
		By default, call self.onselect (but do not do so
		if trigger_callback=False - this mode will not
		normally be needed but is used internally in onmove() )
		"""
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
		"""
		force an update of the background (relevant for useblit=True mode only)
		"""
		if self.useblit:
			self.background = self.canvas.copy_from_bbox( self.ax.bbox )

	def ignore( self, event, v ):
		"""
		return True if event should be ignored
		"""
		if event.inaxes != self.ax or not self.visible or event.button != 1: return True
		sibs = self.sibs()
		nearest = None
		dmin = None
		for sib in self.sibs():
			d = min( abs( lim - v ) for lim in sib.get() )
			if dmin == None or d < dmin: dmin = d; nearest = sib
		return ( self is not nearest )

	def focus( self ):
		"""
		Helper method: ensure that this selector's host axes object has keyboard focus.
		"""
		sibs = self.sibs()
		sibs.remove( self )
		sibs.append( self )
		self.ax.figure.sca( self.ax )
		try: self.ax.figure.canvas._tkcanvas.focus_set()
		except: pass

	def press( self, event ):
		"""
		matplotlib mouse-button-press callback, registered during new_axes() using the matplotlib canvas's mpl_connect() method
		"""
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
		"""
		matplotlib mouse-button-release callback, registered during new_axes() using the matplotlib canvas's mpl_connect() method
		"""

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
		"""
		matplotlib mouse-moved callback, registered during new_axes() using the matplotlib canvas's mpl_connect() method
		Calls set() and hence update().
		"""
		x, y = event.xdata, event.ydata
		if self.direction == 'horizontal': v = x
		else:                              v = y
		if self.pressv is None or v is None or not self.buttonDown: return
		self.prev = x, y
		self.set( ( self.round( v ), self.round( self.pressv ) ), trigger_callback=False )
		return False

	def update( self ):
		"""
		(Re-)render using newfangled blit or oldfangled draw depending on useblit.
		Called automatically by set(), which is in turn called during onmove()
		"""
		if self.useblit:
			if self.background is not None: self.canvas.restore_region( self.background )
			self.ax.draw_artist( self.rect )
			self.canvas.blit( self.ax.bbox )
		else:
			self.canvas.draw_idle()
		return False

	def update_text( self ):
		"""
		Separate update() function for the text label artists. Called automatically by set()
		when appropriate.
		"""
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
		"""
		Return, as a two-element sequence, the current axes' axis limits in the relevant direction.
		"""
		if self.direction == 'horizontal': return self.ax.get_xlim()
		else:                              return self.ax.get_ylim()

	def round( self, value ):
		"""
		Helper method: if self.granularity has been set, return an accordingly round()ed
		version of the input <value>.
		"""
		gran = self.granularity
		#lims = self.axislimits()
		#gran = max( abs( x ) for x in lims ) * self.granularity
		if not gran: return value
		return gran * round( value / gran )

class MVC( object ):
	"""
	An object which manages the graphical/interactive analysis of a Voluntary Contraction
	run with the aim of finding the maximum voluntary contraction (MVC). An MVC instance
	is created by an AnalysisWindow object when its mode is 'vc'.
	"""
	def __init__( self, data, fs, axes=None, callback=None ):
		"""
		Create the necessary matplotlib artists  (no Tk code or objects here)

		<data>     : a list of EMG values, one per SampleBlock
		<fs>       : the sampling rate of <data>, i.e. the SampleBlock rate (not the raw sampling rate of the BCI2000 signal)
		<axes>     : optionally specify an existing matplotlib axes to draw on
		<callback> : function to be called whenever the StickySpanSelector self.selector changes
		"""
		if axes == None: axes = matplotlib.pyplot.gca()
		else: matplotlib.pyplot.figure( axes.figure.number ).sca( axes )
		self.axes = axes
		self.data = data
		self.fs = fs
		self.callback = callback
		self.time = TimeBase( self.data, fs=self.fs, lookback=0 )
		self.line = matplotlib.pyplot.plot( self.time, self.data )[ 0 ]
		self.axes.grid( True )
		peaktime = self.time[ self.data.index( max( self.data ) ) ]
		self.selector = StickySpanSelector( self.axes, initial=( peaktime - 0.1, peaktime + 0.1 ), onselect=self.callback, granularity=0.050, units='s', fmt='%g', color='#FF6666', text_y=0.98, text_verticalalignment='top', text_visible=False )
		self.ycon = AxisController( self.axes, 'y', fmt='%g', units='V', start=self.axes.get_ylim(), narrowest=self.axes.get_ylim() ).Home()
		self.xcon = AxisController( self.axes, 'x', fmt='%g', units='s', start=self.axes.get_xlim(),    widest=self.axes.get_xlim() ).Home()
		self.xcon.focusFunction = self.selector.get
		self.cid = self.axes.figure.canvas.mpl_connect( 'key_press_event', self.KeyPress )
		self.Update()

	def KeyPress( self, event ):
		"""
		This callback is registered with matplotlib during construction so that the
		operator can press escape to zoom all the way out.
		"""
		code = str( event.key ).split( '+' )[ -1 ]
		if code in [ 'escape' ]:
			self.xcon.set( self.xcon.widest )
			if self.callback:
				self.callback() # calls AnalysisWindow.Changed() which leads to AnalysisWindow.UpdateResults() in due course, and that updates the state of the plusminus widget in addition to redrawing the figure
			else:
				self.Update()
				self.axes.figure.canvas.draw()
			return False
		return True

	def Update( self, range=None ):
		"""
		Compute and display the maximum EMG signal associated with voluntary contraction.
		Called by AnalysisWindow.UpdateResults()
		"""
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
	"""
	An object which manages the graphical/interactive analysis of a Recruitment Curve,
	Control Trials and Training Trials run by plotting overlaid EMG traces, with the
	aim of allowing the operator to specify the timing of the intervals of interest.
	A ResponseOverlay instance is created by an AnalysisWindow object when its mode is
	'rc', 'ct' or 'tt', and rendered in the upper tab marked "Timing".
	"""
	def __init__( self, data, fs, lookback, channel=0, axes=None, responseInterval=( .028, .035 ), comparisonInterval=None, prestimulusInterval=None, color='#0000FF', updateCommand=None, rectified=False, emphasis=() ):
		"""
		Each data[ trialIndex ][ channelIndex ][ sampleIndex ] is a floating-point number.
		"""
		if axes == None: axes = matplotlib.pyplot.gca()
		else: matplotlib.pyplot.figure( axes.figure.number ).sca( axes )
		self.axes = axes
		axes.grid( True )
		self.yController = AxisController( axes, 'y', units='V', start=( -0.100, +0.100 ), narrowest=( -0.0001, +0.0001 ), widest=( -20.000, +20.000 ) )
		self.xController = AxisController( axes, 'x', units='s', start=( -0.020, +0.100 ), narrowest=( -0.002,  +0.010  ), widest=( -0.100, +0.500 ) )
		if comparisonInterval == None:  self.comparisonSelector  = None
		else:                           self.comparisonSelector  = StickySpanSelector( axes, onselect=updateCommand, initial=comparisonInterval,  fmt='%g', units='s', granularity=0.0001, color='#AA5500', text_verticalalignment='bottom', text_y=1.00 )
		if prestimulusInterval == None: self.prestimulusSelector = None
		else:                           self.prestimulusSelector = StickySpanSelector( axes, onselect=updateCommand, initial=prestimulusInterval, fmt='%g', units='s', granularity=0.0001, color='#777777', text_verticalalignment='top',    text_y=0.98 )
		if responseInterval == None:    self.responseSelector    = None
		else:                           self.responseSelector    = StickySpanSelector( axes, onselect=updateCommand, initial=responseInterval,    fmt='%g', units='s', granularity=0.0001, color='#008800', text_verticalalignment='top',    text_y=0.98 )
		self.data = data
		self.channel = channel
		self.fs = fs
		self.lookback = lookback
		self.lineprops = {
			-1 : Bunch( color='#000000', alpha=0.0, zorder=2, linewidth=1 ),
			 0 : Bunch( color=color,     alpha=0.3, zorder=2, linewidth=1 ),
			+1 : Bunch( color='#FF00FF', alpha=0.8, zorder=3, linewidth=2 ),
		}
		self.lines = []
		self.emphasis = list( emphasis )
		for trial in self.data:
			values = trial[ self.channel ]
			self.lines += matplotlib.pyplot.plot( TimeBase( values, self.fs, self.lookback ), values, **self.lineprops[ 0 ] )
			if not len( emphasis ): self.emphasis.append( 0 )
		self.yController.Home()
		self.xController.Home()
		self.Update( rectified=rectified )

	def Update( self, rectified=None, color=None, channel=None ):
		"""
		Update the display. Called by AnalysisWindow.UpdateResults()
		"""
		if rectified != None: self.rectified = rectified
		if color != None: self.lineprops[ 0 ].color = color
		if channel != None: self.channel = channel
		for trial, line, emphasis in zip( self.data, self.lines, self.emphasis ):
			if self.rectified: line.set_ydata( [ abs( value ) for value in trial[ self.channel ] ] )
			else: line.set_ydata( trial[ self.channel ] )
			line.set( **self.lineprops[ emphasis ] )
		ylim = self.axes.get_ylim()
		if self.rectified: self.axes.set_ylim( [ 0, ylim[ 1 ] ] )
		else: self.axes.set_ylim( [ -ylim[ 1 ], ylim[ 1 ] ] )

	def ResponseMagnitudes( self, type='target', p2p=False ):
		"""
		Compute trial-by-trial response magnitudes from the data stored in this object,
		either as mean rectified EMG (p2p=False) or peak-to-peak values (p2p=True).
		type='prestimulus' : pre-stimulus interval
		type='comparison'  : use the comparison (aka "reference") response interval
		type='response'    : use the target response interval

		(Note that these keywords, like many of the attribute/variable names in the code,
		reflect an older convention, whereas in the user interface and in the documentation
		these should consistently be referred to as "pre-stimulus", "reference" response
		and "target" response respectively.)
		"""
		if   type == 'response':    interval = self.responseSelector.get()
		elif type == 'comparison':  interval = self.comparisonSelector.get()
		elif type == 'prestimulus': interval = self.prestimulusSelector.get()
		return ResponseMagnitudes( data=self.data, channel=self.channel, interval=interval, fs=self.fs, lookback=self.lookback, p2p=p2p )

class ResponseSequence( object ):
	"""
	An object which manages the graphical/interactive analysis of a Recruitment Curve,
	Control Trials and Training Trials run by plotting reference response magnitude
	and target response magnitude sequentially, i.e. as a function of trial index.
	A ResponseSequence instance is created by an AnalysisWindow object when its mode is
	'rc', 'ct' or 'tt', and rendered in the lower tab marked "Sequence".
	"""
	def __init__( self, overlay, axes=None, pooling=1, p2p=False, tk=False,xlabels=[],StimPool=1):
		"""
		Render the necessary matplotlib artists and TkInter widgets.

		<overlay> is a ResponseOverlay instance, from which the data will be taken.
		<axes>    is an optional matplotlib.pyplot.axes instance to draw into
		<pooling> is the number of trials to pool initially
		<p2p>     is a boolean flag dictating whether to use averaged rectified
				  magnitude (p2p=False) or peak-to-peak magnitude (p2p=True)
		<tk>      is a TkInter widget to draw into:  if supplied, create TkInter.Label
				  instances (via the InfoItem class) for displaying the computed information.
		"""
		if axes == None: axes = matplotlib.pyplot.gca()
		else: matplotlib.pyplot.figure( axes.figure.number ).sca( axes )
		self.axes = axes
		self.overlay = overlay
		self.pooling = pooling
		self.stimpool = StimPool
		self.nremoved = 0
		self.p2p = p2p
		self.frame = None
		prestimColor = self.overlay.prestimulusSelector.rectprops[ 'facecolor' ]
		comparisonColor = self.overlay.comparisonSelector.rectprops[ 'facecolor' ]
		responseColor = self.overlay.responseSelector.rectprops[ 'facecolor' ]
		if tk:
			widget = self.axes.figure.canvas.get_tk_widget()
			if isinstance( tk, tkinter.Widget ): self.frame = tk
			else: self.frame = tkinter.Frame( widget, bg=widget[ 'bg' ] )
		self.panel = Bunch(
			  bg=InfoItem( 'Mean\npre-stimulus',      0, fmt='%.1f', units='V', color=prestimColor    ).tk( self.frame, row=1 ),
			mmax=InfoItem( 'Max reference\nresponse', 0, fmt='%.1f', units='V', color=comparisonColor ).tk( self.frame, row=2 ),
			hmax=InfoItem( 'Max target\nresponse',    0, fmt='%.1f', units='V', color=responseColor   ).tk( self.frame, row=3 ),
		)
		if self.frame:
			for row in range( 3 ): self.frame.grid_rowconfigure( row + 1, weight = 1 )
			self.frame.grid_columnconfigure( 2, weight = 1 )
			if not isinstance( tk, tkinter.Widget ):
				AxesPosition( self.axes, right=0.75 )
				p = AxesPosition( self.axes ); rgap = 1.0 - p.right
				self.frame.place( in_=widget, relx=1.0 - rgap / 2.0, rely=1.0 - p.bottom - p.height/2, relheight=p.height*1.1, anchor='center' )
		self.Update(xlabels=xlabels)

	def Update( self, pooling=None, p2p=None,xlabels=[]):

		"""
		Update the display. Called by AnalysisWindow.UpdateResults()
		"""
		if pooling != None: self.pooling = pooling
		if p2p != None: self.p2p = p2p
		def pool( x, pooling, emphasis=None ):
			ni, n, pooled = pooling, [], []
			for start in range( 0, len( x ) - pooling + 1, pooling ):
				xsub = x[ start : start + pooling ]
				if emphasis != None:
					keep = [ em >= 0 for em in emphasis[ start : start + pooling ] ]
					if sum( keep ): xsub = [ eachVal for eachVal, keepEachVal in zip( xsub, keep ) if keepEachVal ]
					# do not remove any if you would remove *all* in the current pool (if that's the case, this data-point will be excluded completely from analysis later on anyway, but let's compute where it would have been)
				pooled.append( sum( xsub ) / float( len( xsub ) ) )
				n.append( ni ); ni += pooling
			return n, pooled
		def autopool(c, x ):
			#autopool uses currents (xlabel) to automaticall group responses
			Currents = numpy.asarray([float(i) for i in c])
			UniqueC = numpy.unique(Currents)
			UniqueC = UniqueC.tolist()

			xh, pooled = [], []
			for i in range(0, len(UniqueC)):
				xh.append('{:.2f}'.format(UniqueC[i]))
				w = numpy.where(Currents == UniqueC[i])[0]
				pooled.append(sum(numpy.extract(Currents == UniqueC[i], x)) / len(w))

			return xh, pooled

		xh, h = pool( self.overlay.ResponseMagnitudes( p2p=self.p2p, type='response'   ),  pooling=self.pooling, emphasis=self.overlay.emphasis )
		xm, m = pool( self.overlay.ResponseMagnitudes( p2p=self.p2p, type='comparison' ),  pooling=self.pooling, emphasis=self.overlay.emphasis )
		xRemoved, removed = pool( [ float( emph < 0 ) for emph in self.overlay.emphasis ], pooling=self.pooling )
		xHilited, hilited = pool( [ float( emph > 0 ) for emph in self.overlay.emphasis ], pooling=self.pooling )

		b = self.overlay.ResponseMagnitudes( p2p=self.p2p, type='prestimulus' )
		self.n = len( b )
		self.nremoved = sum( [ emphasis < 0 for emphasis in self.overlay.emphasis ] )

		matplotlib.pyplot.figure( self.axes.figure.number ).sca( self.axes )
		matplotlib.pyplot.cla()
		mMax = hMax = bSum = bNum = 0.0
		for x, hVal, mVal, bVal, proportionRemoved, proportionHilited in zip( xRemoved, h, m, b, removed, hilited ):
			hHandle, = matplotlib.pyplot.plot( x, hVal, linestyle='none', marker='o', markersize=10, color=self.overlay.responseSelector.rectprops[ 'facecolor' ] )
			mHandle, = matplotlib.pyplot.plot( x, mVal, linestyle='none', marker='^', markersize=10, color=self.overlay.comparisonSelector.rectprops[ 'facecolor' ] )
			if proportionHilited > 0.001: [ handle.set( markeredgecolor=self.overlay.lineprops[ +1 ].color, markeredgewidth=2 ) for handle in hHandle, mHandle ]
			if proportionHilited > 0.999: [ handle.set( markerfacecolor=self.overlay.lineprops[ +1 ].color ) for handle in hHandle, mHandle ]
			if proportionRemoved > 0.001: [ handle.set( alpha=0.5 ) for handle in hHandle, mHandle ]
			if proportionRemoved > 0.999: [ handle.set( markerfacecolor='#FFFFFF' ) for handle in hHandle, mHandle ]
			else:
				mMax = max( mVal, mMax )
				hMax = max( hVal, hMax )
				bSum += bVal
				bNum += 1.0

		self.yController = AxisController( self.axes, 'y', units='V', fmt='%g', start=self.axes.get_ylim() )
		self.yController.ChangeAxis( start=( 0, max( self.axes.get_ylim() ) ) )
		self.axes.grid( True )
		xt = list( xh )
		while len( xt ) > 15: xt = xt[ 1::2 ]
		self.axes.set( xlim=( 0	, max( xh ) + 1 ))#, title='Left-click to toggle highlighting; right-click to toggle removal' )

		self.axes.set_xticks(xt)

		if xlabels != []:
			x = [xlabels[i - 1] for i in xt]
			self.axes.set_xticklabels(x)

		# Section for a text box, that shows the M and H values for any selected points.
		# Adding a text overlay for the H and M values

		for i in range(0, len(self.axes.texts)):
			self.axes.texts.remove(self.axes.texts[i])
		# Broken down into which of the sequence need to be measured
		indEmphasis = [self.overlay.emphasis[i] for i in
					   range(self.pooling - 1, len(self.overlay.emphasis), self.pooling)]
		indSelected = [i for i, j in enumerate(indEmphasis) if j == 1]

		if indSelected != []:
			Mvalue = ', '.join('{:.2f}'.format(m[i] * 1000) for i in indSelected)
			Hvalue = ', '.join('{:.2f}'.format(h[i] * 1000) for i in indSelected)

			# Mvalue = '{:.2f}'.format(self.axes.lines[indSelected].get_data()[1].tolist()[0] * 1000)
			# Hvalue = '{:.2f}'.format(self.axes.lines[indSelected-1].get_data()[1].tolist()[0] * 1000)
			self.axes.text(0.02, 0.9, 'M: ' + Mvalue + 'mV',
						   bbox=dict(facecolor=self.overlay.comparisonSelector.rectprops['facecolor'], alpha=0.5),
						   fontsize=12, transform=self.axes.transAxes)
			self.axes.text(0.02, 0.83, 'H: ' + Hvalue + 'mV',
						   bbox=dict(facecolor=self.overlay.responseSelector.rectprops['facecolor'], alpha=0.5),
						   fontsize=12, transform=self.axes.transAxes)

		self.panel.bg.set( bSum / max( bNum, 1.0 ) )
		self.panel.mmax.set( mMax )
		self.panel.hmax.set( hMax )

class ResponseDistribution( object ):
	"""
	An object which manages the graphical/interactive analysis of a Recruitment Curve,
	Control Trials and Training Trials run by plotting a histogram of target response
	magnitudes.
	A ResponseDistribution instance is created by an AnalysisWindow object when its mode
	is 'rc', 'ct' or 'tt', and rendered in the lower tab marked "Distribution".
	"""
	def __init__( self, overlay, axes=None, targetpc=66, nbins=10, p2p=False, tk=False ):
		"""
		Render the necessary matplotlib artists and TkInter widgets.

		<overlay>  is a ResponseOverlay instance, from which the data will be taken.
		<axes>     is an optional matplotlib.pyplot.axes instance to draw into
		<targetpc> is the initial target percentile for specifying training targets
		<nbins>    is the number of bins in the histogram
		<p2p>      is a boolean flag dictating whether to use averaged rectified
		           magnitude (p2p=False) or peak-to-peak magnitude (p2p=True)
		<tk>       is a TkInter widget to draw into:  if supplied, create TkInter widgets
		           (via the InfoItem class) for displaying the computed information.
		"""
		if axes == None: axes = matplotlib.pyplot.gca()
		else: matplotlib.pyplot.figure( axes.figure.number ).sca( axes )
		self.axes = axes
		self.overlay = overlay
		self.targetpc = targetpc
		self.nbins = nbins
		self.nremoved = 0
		self.p2p = p2p
		self.frame = None
		prestimColor = self.overlay.prestimulusSelector.rectprops[ 'facecolor' ]
		comparisonColor = self.overlay.comparisonSelector.rectprops[ 'facecolor' ]
		responseColor = self.overlay.responseSelector.rectprops[ 'facecolor' ]
		if tk:
			widget = self.axes.figure.canvas.get_tk_widget()
			if isinstance( tk, tkinter.Widget ): self.frame = tk
			else: self.frame = tkinter.Frame( widget, bg=widget[ 'bg' ] )
		self.panel = Bunch(
			          n=InfoItem( 'Number\nof Trials',                  0, fmt='%g'                                     ).tk( self.frame, row=1 ),
			prestimulus=InfoItem( 'Pre-stimulus\n(Median, Mean)',       0, fmt='%.1f', units='V', color=prestimColor    ).tk( self.frame, row=2 ),
			 comparison=InfoItem( 'Reference Response\n(Median, Mean)', 0, fmt='%.1f', units='V', color=comparisonColor ).tk( self.frame, row=3 ),
			   response=InfoItem( 'Target Response\n(Median, Mean)',    0, fmt='%.1f', units='V', color=responseColor   ).tk( self.frame, row=4 ),
			   uptarget=InfoItem( 'Upward\nTarget',                     0, fmt='%.1f', units='V'                        ).tk( self.frame, row=6 ),
			 downtarget=InfoItem( 'Downward\nTarget',                   0, fmt='%.1f', units='V'                        ).tk( self.frame, row=7 ),
		)
		if self.frame:
			self.entry = InfoItem( 'Target\nPercentile', self.targetpc, fmt='%g' ).tk( self.frame, row=5, entry=True )
			for row in range( 6 ): self.frame.grid_rowconfigure( row + 1, weight = 1 )
			self.frame.grid_columnconfigure( 2, weight = 1 )
			if not isinstance( tk, tkinter.Widget ):
				AxesPosition( self.axes, right=0.65 )
				p = AxesPosition( self.axes ); rgap = 1.0 - p.right
				self.frame.place( in_=widget, relx=1.0 - rgap * 0.4, rely=1.0 - p.bottom - p.height/2, relheight=p.height*1.1, anchor='center' )
		self.Update()

	def Update( self, nbins=None, targetpc=None, p2p=None ):
		"""
		Update the display. Called by AnalysisWindow.UpdateResults()
		"""
		if nbins != None: self.nbins = nbins
		if targetpc != None: self.targetpc = targetpc
		if p2p != None: self.p2p = p2p

		def ResponseStats( type ):
			x = self.overlay.ResponseMagnitudes( p2p=self.p2p, type=type )
			x = [ xi for xi, emphasis in zip( x, self.overlay.emphasis ) if emphasis >= 0 ]
			xSorted = sorted( x )
			if len( x ) == 0: xMedian = xMean = 0.0
			else:
				xMean = sum( x ) / float( len ( x ) )
				xMedian = Quantile( xSorted, 0.5, alreadySorted=True )
			return x, xSorted, xMean, xMedian
		self.nremoved = sum( [ emphasis < 0 for emphasis in self.overlay.emphasis ] )
		r, rSorted, rMean, rMedian = ResponseStats( 'response' )
		c, cSorted, cMean, cMedian = ResponseStats( 'comparison' )
		b, bSorted, bMean, bMedian = ResponseStats( 'prestimulus' )
		n = len( r )
		if n: targets = Quantile( rSorted, ( self.targetpc / 100.0, 1.0 - self.targetpc / 100.0 ), alreadySorted=True )
		else: targets = [ 0 ]
		downtarget, uptarget = max( targets ), min( targets )
		matplotlib.pyplot.figure( self.axes.figure.number ).sca( self.axes )
		matplotlib.pyplot.cla()
		#print 'calculated = ' + repr( r )
		if len( r ) == 1: extra = dict( range=[ r[ 0 ] * 0.9, r[ 0 ] * 1.1 ] )
		else: extra = {}
		if len( r ): self.counts, self.binCenters, self.patches = matplotlib.pyplot.hist( r, bins=self.nbins, facecolor=self.overlay.lineprops[ 0 ].color, edgecolor='none', **extra )
		else: self.counts, self.binCenters, self.patches = [], [], []
		self.xController = AxisController( self.axes, 'x', units='V', fmt='%g', start=self.axes.get_xlim() )
		self.xController.Home()
		vals = [ downtarget, uptarget, rMean ]
		self.downline, self.upline, self.meanline = matplotlib.pyplot.plot( [ vals, vals ], [ [ 0 for v in vals ], [ 1 for v in vals ] ], color='#FF0000', linewidth=4, alpha=0.5, transform=self.axes.get_xaxis_transform() )
		self.panel.n.set( n )
		self.panel.prestimulus.set( [ bMedian, bMean ] )
		self.panel.comparison.set(  [ cMedian, cMean ] )
		self.panel.response.set(    [ rMedian, rMean ] )
		self.panel.uptarget.set( uptarget )
		self.panel.downtarget.set( downtarget )
		if self.nremoved: self.axes.set_title( '%d of %d trials removed' % ( self.nremoved, self.nremoved + n ) )
		else: self.axes.set_title( '' )

class TableButton(object):
	# A simple table with a "button" in the last column that enables a function to be generated

	def __init__(self,parent,overlay=None,List=None,Headings=None,Frame=None,ButtonHeader=''):

		#This assumes that if you want to add a button the Headings will not indicate this and need to be added
		self.Index = '' #Name of Location in Question to be used in
		self.overlay = overlay
		if Frame == None:
			Frame = tkinter.Frame(self)

		self.CreateTable(list=List,frame=Frame,headings=Headings,buttonHeader=ButtonHeader)

	def CreateTable(self,list,frame,headings,buttonHeader):

		if buttonHeader != '':
			headings.append(buttonHeader)

		self.tree = ttk.Treeview(frame, columns=headings[1:len(headings)])

		ttk.Style().configure('.', relief='flat', borderwidth=0)

		self.tree.heading('#0', text=headings[0], anchor='w')
		self.tree.column('#0', width=100, stretch=0)
		for n in range(1,len(headings)):
			self.tree.heading(headings[n], text=headings[n], anchor='w')
			self.tree.column(headings[n], width=100, stretch=0)

		if buttonHeader != '':
			self.tree.bind("<Double-1>", self.OnDoubleClick)  # double click bind

		self.tree.bind("<<TreeviewSelect>>", self.OnSingleClick) #single click select bind

		for key, value in list.iteritems():
			if buttonHeader != '':
				value = [str(value),'No']
			self.tree.insert('','end', text=key,values=value)

		self.tree.grid(row=0, column=0,columnspan=4, sticky='new')

		frame.rowconfigure(0, weight=1)
		frame.columnconfigure(0, weight=1)

	def OnSingleClick(self,event):
		selection = self.tree.selection()
		text = self.tree.item(selection)['text']
		if self.Index == '':
			self.Index = text
			self.ToggleTrial(event=event,newValue=+1)
		elif text == self.Index:
			self.tree.selection_remove(selection)
			self.ToggleTrial(event=event, newValue=-1)
			self.Index = ''

	def OnDoubleClick(self,event):
		s = self.tree.selection()[0]
		self.TogglePlot(s)

	def TogglePlot(self,selection):
		vStatus = self.tree.set(selection, 'Plot')
		if 'No' in vStatus: vStatus = 'Yes'
		else: vStatus = 'No'
		self.tree.set(selection, 'Plot', value=vStatus)

	def ToggleAll(self,YES=True):
		c = self.tree.get_children()
		c = self.tree.get_children()
		for item in c:
			if YES: self.tree.set(item, 'Plot', value='Yes')
			else: self.tree.set(item, 'Plot', value='No')

	def ToggleTrial( self, event, newValue=0):
		"""
		Callback registered as the matplotlib mouse-button-press event handler for any analysis
		window that implements a ResponseSequence object. Allows highlighting to be toggled
		with the left mouse button, and removal with the right button.
		"""
		indices = int(round( event.x ))
		if (len(self.overlay.emphasis) > 0):
			for index in indices: self.overlay.emphasis[ index ] = newValue
			self.overlay.Update()
			ax = self.parent.artists.get('overlay_axes_main', None)
			if ax: matplotlib.pyplot.figure(ax.figure.number).sca(ax)
			self.parent.DrawFigures()

		return False



	def DeleteItem(self,selected_item=None):
		if selected_item == None:
			selected_item = self.tree.selection()[0]
		self.tree.delete(selected_item)

	def AddNewItem(self,Names,itemValues):

		for name,item in zip(Names,itemValues):
			self.tree.insert("","end",text=name,values=item)

class InfoItem( TkMPL ):
	"""
	A class representing a labelled piece of information which has a label and a value
	that are both made visible to the user.  These are used by the ResponseSequence and
	ResponseDistribution classes to display statistics that have been computed from the
	data.   Can also be a labelled text *input* rather than output (for the "target
	percentile" setting) but this functionality is not as sophisticated as that in the
	LabelledEntry class.
	"""
	def __init__( self, label, value, fmt='%s', units=None, color='#000000' ):
		TkMPL.__init__( self )
		self.label = label
		self.value = value
		self.fmt = fmt
		self.units = units
		self.color = color
	def str( self, value=None, appendUnits=True ): # do not call this  __str__ : in Python 2.5, that gives a unicode conversion error when there's a microVolt symbol in the string
		if value == None:
			if self.widgets.get( 'variable', None ):
				self.value = self.widgets.variable.get()
				try: self.value = float( self.value )
				except: pass
			value = self.value
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
	def tkc( self, parent, column, entry=False ): ###AMIR Exactly as in tk() but this let's you place them in one row so input is column not row
		if parent == None: return self
		self.widgets.label = tkinter.Label( parent, text=self.label, justify='right', bg=parent[ 'bg' ], fg=self.color , font = ( 'Helvetica', 15 , 'bold'))
		if entry:
			self.widgets.variable = tkinter.Variable( parent, value=self.str() )
			self.widgets.value = tkinter.Entry( parent, textvariable=self.widgets.variable, bg='#FFFFFF' )
		else:
			self.widgets.variable = None
			self.widgets.value = tkinter.Label( parent, text=self.str(), bg=parent[ 'bg' ], fg=self.color ,font = ( 'Helvetica', 15, ))
		self.widgets.label.grid( row=1, column=column, sticky='nse', padx=5, pady=2 )
		self.widgets.value.grid( row=1, column=column+1, sticky='w',   padx=5, pady=2 )
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

class LabelledEntry( ConnectedWidget ):
	"""
	A helper subclass, derived from ConnectedWidget, used heavily by the SettingsWindow class.
	It instantiates tkinter widgets for a label adjacent to a text input field.  It also
	allows you to connect() the value entered in the text field to a certain .resource
	(which could be a dict or Bunch - in fact we use the .params Bunch from an Operator
	class, where session settings are stored).  Thereafter, the LabelledEntry can pull()
	its value from that resource or push() it back.
	"""
	def __init__( self, parent, label, value='', width=5, bg=None ):
		ConnectedWidget.__init__( self, parent, bg=bg )
		self.label = tkinter.Label( self, text=label, bg=bg, justify='right' )
		self.entry = tkinter.Entry( self, width=width, textvariable=self.variable, bg='#FFFFFF' )
		if len( label ):
			self.label.pack( side='left', padx=3 )
			self.entry.pack( side='left', padx=3 )
		else:
			self.entry.pack( padx=3 )

