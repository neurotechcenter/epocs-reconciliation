import matplotlib
import Tkinter as tkinter
try: import ttk
except ImportError: import Tix; tksuperclass = Tix.Tk  # ...because Python 2.5 does not have ttk. Included for legacy compatibility:  this GUI was originally developed under Python 2.5.4 without ttk, but has now transitioned to Python 2.7.5 with ttk
import sys
from CoreFunctions import Bunch, FixAspectRatio


class TkMPL( object ):
	"""
	This is a general class that allows you to keep track of a lot of Tkinter widgets
	(in a Bunch() called self.widgets) and a lot of matplotlib artists (in a Bunch()
	called self.artists).  Subsets of them can be retrieved by the MatchWidgets() and
	MatchArtists() methods.

	The convention is to use the Bunch() key to code a number of different specifiers,
	delimited by underscores. Typically this will be a location or context, followed by
	a type, followed by an individual identifier - for example, self.artists.st_axes_emg1
	is the matplotlib artist of type axes, located on the 'st' (Stimulus Test) tab, and
	specifically for the purpose of displaying the first EMG signal.  That particular
	pointer will be returned among the artists whenever 'st' and/or 'axes' and/or
	'emg1' are included in the input terms to self.MatchArtists().   Sometimes there
	will exist both a widget and an artist for the same logical object:  for example,
	the NewFigure() method called with prefix='st' and suffix='main' creates both
	self.artists.st_figure_main (the matplotlib figure handle for the main figure on the
	Stimulus Test tab) and self.widgets.st_figure_main (the Tkinter widget that the
	matplotlib back-end creates for that same figure's canvas).

	In addition to MatchArtists() and MatchWidgets() for element management,  methods
	include NewFigure() as mentioned above,  DrawFigures() for refreshing/redrawing all
	(or a subset of) the handles that can be retrieved by self.MatchArtists( 'figure' );
	and several helper methods for creating and manipulating tabbed panes in the GUI.

	The TkMPL class is an abstract class, used as superclass for the main GUI() class,
	as well as the AnalysisWindow() and SettingsWindow(), and also the InfoItem() helper
	class.
	"""
	def __init__( self ):
		self.artists = Bunch()
		self.widgets = Bunch()
		self.colors = Bunch(  # also define the colour-scheme.  Note that HTML-style colour strings are accepted by both Tkinter and matplotlib, so let's stick to that format
			           figure = '#CCCCCC',
			               bg = '#CCCCCC',
			               fg = '#000000',
			           button = '#DDDDDD',
			         disabled = '#777777',
			         backpage = '#888888',
			         progress = '#CCCCCC',
			         controls = '#DDDDDD',
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
		"""
		Helper function for MatchArtists() and MatchWidgets()
		"""
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
		"""
		Return all matplotlib artists that contain all the *terms, underscore-delimited,
		in their keys.  For example,  if self is a GUI() instance, then
		self.MatchArtists( 'axes', 'st' ) will return all matplotlib artists that are of
		type 'axes' on the 'st' (Stimulus Test) tab, i.e. it will return
		[ self.artists.st_axes_emg1, self.artists.st_axes_emg2 ]
		"""
		keys, things = self.Match( self.artists, *terms )
		return things

	def MatchWidgets( self, *terms ):
		"""
		Similar to MatchArtists, but retrieves Tkinter widgets from self.widgets instead of
		matplotlib artists from self.artists
		"""
		keys, things = self.Match( self.widgets, *terms )
		return things

	def DrawFigures( self, *terms ):
		"""
		Refresh/redraw all the matplotlib 'figure' artists registered in self.artists
		If optional *terms are supplied, use these to narrow the list of figures-to-
		redraw further, as per MatchArtists().
		"""
		for fig in self.MatchArtists( 'figure', *terms ): fig.canvas.draw()

	def NewFigure( self, parent, prefix, suffix, fig=None, color=None, **kwargs ):
		"""
		Create a figure, registering both a matplotlib artist and a Tkinter widget
		For example, the NewFigure() method called with prefix='st' and suffix='main'
		creates both self.artists.st_figure_main (the matplotlib figure handle for
		the main figure on the Stimulus Test tab) and self.widgets.st_figure_main
		(the Tkinter widget that the matplotlib back-end creates for that same
		figure's canvas).
		<parent> is the Tkinter.Frame in which the new figure should be rendered.
		"""
		name = prefix + '_figure_' + suffix
		if fig: matplotlib.pyplot.figure( fig.number )
		else: fig = matplotlib.pyplot.figure()
		container = tkinter.Frame( parent, bg=parent[ 'bg' ] )
		matplotlib.backends.backend_tkagg.FigureCanvasTkAgg( fig, master=container ) # replaces fig.canvas
		widget = fig.canvas.get_tk_widget()
		if color == None: color = self.colors.figure
		if color == None: color = widget.master[ 'bg' ]
		fig.patch.set_edgecolor( color )
		fig.patch.set_facecolor( color )
		widget.configure( bg=color, borderwidth=0, insertborderwidth=0, selectborderwidth=0, highlightthickness=0, insertwidth=0 )
		container.configure( width=800, height=600 )
		if len( kwargs ): container.configure( **kwargs )
		FixAspectRatio( widget, float( container[ 'height' ] ) / float( container[ 'width' ] ) ) #, relx=0.0, anchor='w' )
		self.artists[ name ] = fig
		self.widgets[ name ] = widget
		fig.subplots_adjust( bottom=0.06, top=0.94, right=0.92 )
		return fig, widget, container

	def MakeNotebook( self, parent=None, name='notebook' ):
		"""
		Creates a tabbed notebook widget using ttk.Notebook() if the
		built-in ttk module is available (Python 2.7) or as a somewhat
		clunkier Tix.Notebook if not (Python 2.5).

		<parent> may be a Tkinter widget, or None.
		<name> specifies the key under which the resulting notebook widget
		is stored in self.widgets.

		Use the TkMPL methods AddTab(), EnableTab() and SelectTab() to
		configure and manipulate the notebook's tabs.
		"""
		if parent == None: parent = self
		if 'ttk' in sys.modules:
			notebook = self.widgets[ name ] = ttk.Notebook( parent )
		else:
			notebook = self.widgets[ name ] = Tix.NoteBook( parent, name=name, ipadx=6, ipady=6 )
			notebook[ 'bg' ] = notebook.nbframe[ 'bg' ] = self.colors.bg
			notebook.nbframe[ 'backpagecolor' ] = self.colors.backpage
		return notebook

	def AddTab( self, key, title, makeframe=True, nbname='notebook' ):
		"""
		Create a new tab, stored in self.widgets under the specified
		<key> (to which '_tab' is automatically appended). Render the <title>
		text on the tab itself, and unless makeframe=False, make a Tkinter.Frame
		inside the tab, store it in self.widgets under the specified <key> with
		'_frame_main' appended, and return that instead of the raw tab.

		You should specify the appropriate <nbname> if the notebook in question
		was created using a non-default <name> argument to MakeNotebook().
		"""
		if 'ttk' in sys.modules:
			tab = self.widgets[ key + '_tab' ] = tkinter.Frame( self, bg=self.colors.bg )
			tab.pack()
			self.widgets[ nbname ].add( tab, text=' ' + title + ' ', padding=10 )
			if not makeframe: return tab
			frame = self.widgets[ key + '_frame_main'] = tkinter.Frame( tab, bg=self.colors.bg )
			return frame
		else:
			tab   = self.widgets[ key + '_tab' ] = self.widgets[ nbname ].add( name=key + '_tab', label=title, underline=0 )
			tab[ 'bg' ] = self.colors.bg
			if not makeframe: return tab
			frame = self.widgets[ key + '_frame_main' ] = tkinter.Frame( tab, bg=self.colors.bg )
			return frame

	def EnableTab( self, whichTab='all', nbname='notebook' ):
		"""
		Either enable all notebook tabs (whichTab='all') or enable just one tab and
		disable all the others (e.g. whichTab='st' will enable self.widges.st_tab
		and disable its siblings). Disabled tabs cannot be clicked on.

		As for AddTab(), specify <nbname> if the notebook in question was created
		with a custom name.
		"""
		tabNames = [ k for k in self.widgets.keys() if 'tab' in k.lower().split( '_' ) ]
		for tabName in tabNames:
			if whichTab == 'all' or whichTab.lower() in tabName.lower().split( '_' ): state = 'normal'
			else: state = 'disabled'
			if 'mwave' in tabName.lower().split('_'): continue
			if 'ttk' in sys.modules: self.widgets[ nbname ].tab( self.widgets[ tabName ], state=state )
			else: self.widgets[ nbname ].tk.call( self.widgets[ nbname ]._w, 'pageconfigure', tabName, '-state', state )

	def SelectTab( self, whichTab, nbname='notebook' ):
		"""
		Select (i.e. raise above its siblings, as if clicked by the user) the specified
		notebook tab.  For example self.SelectTab( 'st' ) will raise self.widgets.st_tab

		As for AddTab(), specify <nbname> if the notebook in question was created
		with a custom name.
		"""
		tabName = whichTab + '_tab'
		if 'ttk' in sys.modules: self.widgets[ nbname ].select( self.widgets[ tabName ] )
		else: self.widgets[ nbname ].raise_page( tabName )

	def InfoFrame( self, code, name, title, value, size=14, labelsize=10, parent=None, color='#000000' ):
		"""
		Create and lay out a pair of text widgets for displaying a certain piece of
		information in the "control panel" (for example, title='Last Recording:', value'='R01').
		<code>:  the two-letter code for the GUI tab (see the MODENAMES global variable)
		<name>:  the suffix for the key in self.widgets (see the TkMPL class documentation)
		         indicates to the program what this particular info frame is about
		<title>: text indicating to the user what kind information is being displayed
		<value>: text telling the user the information itself
		"""
		if parent == None: parent = self.widgets[ code + '_frame_controls' ]
		frame = self.widgets[ code + '_frame_info_' + name ] = tkinter.Frame( parent, bg=parent[ 'bg' ] )
		tLabel = self.widgets[ code + '_label_title_' + name ] = tkinter.Label( frame, text=title, font=( 'Helvetica', labelsize ), bg=parent[ 'bg' ], fg=color )
		vLabel = self.widgets[ code + '_label_value_' + name ] = tkinter.Label( frame, text=value, font=( 'Helvetica', size ),      bg=parent[ 'bg' ], fg=color )
		tLabel.pack( side='top', fill='both', padx=2, pady=2, expand=1 )
		vLabel.pack( side='bottom', fill='both', padx=2, pady=4, expand=1 )
		return frame

	# def ProgressPanel( self, code, trials=True, success=False ):
	# 	"""
	# 	Create and lay out, on the GUI tab indicated by the two-letter <code>, a frame
	# 	containing a trial counter and (if success=True) a success rate counter.
	# 	"""
	# 	tabkey = code + '_tab'
	# 	tab = self.widgets[ code + '_tab' ]
	# 	frame = self.widgets[ code + '_frame_progress' ] = tkinter.Frame( tab, bg=self.colors.progress )
	# 	if trials: self.InfoFrame( code, 'trial', 'Trials Completed:', '0', parent=frame, labelsize=20, size=70 ).place( relx=0.5, rely=0.1, anchor='n' )
	# 	bg = frame[ 'bg' ]
	# 	display = '----'
	# 	#bg = '#FF0000'; display = '99.9%'  # for debugging
	# 	tkinter.Frame( frame, width=420, height=2, bg=bg ).pack( side='bottom' ) # spacer
	# 	if success: self.InfoFrame( code, 'success', 'Success Rate:', display, parent=frame.master, labelsize=20, size=110 ).place( in_=frame, relx=0.5, rely=0.9, anchor='s' )
	# 	#frame.grid( row=1, column=2, sticky='nsew' )
	# 	frame.pack( side='right', fill='y' )
	# 	return frame

	def ProgressPanel(self, code, trials=True,success=False, parentmode=None):  ###AMIR-A countdown (CD) Progress Panel with +/- to set its initial value
		"""
        Create and lay out, on the GUI tab indicated by the two-letter <code>, a frame
        containing a trial counter and (if success=True) a success rate counter.
        """
		tab = self.widgets[code + '_tab']
		frame = self.widgets[code + '_frame_progress'] = tkinter.Frame(tab, bg=self.colors.progress)

		if parentmode == None: parentmode = code

		UD = getattr(self.operator.params,'_UpDownTrialCount')#Indicates up or down counting

		if 'ct' in parentmode and (UD == 'down'):
			N = int(getattr(self.operator.params, '_' + 'ct' + 'TrialsCount'))
			if trials: self.InfoFrame(code, 'trial', 'Trials Remaining:', str(N), parent=frame, labelsize=20,
									  size=70).place(relx=0.5, rely=0.1, anchor='n')
		elif 'tt' in parentmode and (UD == 'down'):
			N = int(getattr(self.operator.params, '_' + 'tt' + 'TrialsCount'))
			if trials: self.InfoFrame(code, 'trial', 'Trials Remaining:', str(N), parent=frame, labelsize=20,
									  size=70).place(relx=0.5, rely=0.1, anchor='n')
		else:
			self.InfoFrame(code, 'trial', 'Trials Completed:', '0', parent=frame, labelsize=20,size=70).place(relx=0.5, rely=0.1, anchor='n')

		bg = frame['bg']
		display = '----'
		# bg = '#FF0000'; display = '99.9%'  # for debugging
		tkinter.Frame(frame, width=420, height=2, bg=bg).pack(side='bottom')  # spacer
		if success: self.InfoFrame(code, 'success', 'Success Rate:', display, parent=frame.master, labelsize=20,
								   size=110).place(in_=frame, relx=0.5, rely=0.9, anchor='s')
		# frame.grid( row=1, column=2, sticky='nsew' )
		frame.pack(side='right', fill='y')
		return frame