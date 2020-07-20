from matplotlib.ticker import AutoMinorLocator
from CoreGUIcomponents import *

GUIDIR = os.path.dirname( os.path.realpath( inspect.getfile( inspect.currentframe() ) ) ) # GUIDIR is the directory where this executable lives - will also be expected to contain .ico file and .ini files
BCI2000LAUNCHDIR = os.path.abspath( os.path.join( GUIDIR, '../../prog' ) ) # BCI2000LAUNCHDIR contains the BCI2000 binaries: it is expected to be in ../prog relative to this python file

class MWaveAnalysisWindow(tkinter.Toplevel, TkMPL):
    """
    ###AMIR
    An M Wave Analysis Window is created when the "M-Wave Analysis" button is
    pressed on the ct tab of the GUI().
    """

    def __init__(self, parent, mode, operator):

        tkinter.Toplevel.__init__(self)
        TkMPL.__init__(self)

        self.axiscontrollers_emg1 = []
        self.axiscontrollers_emg2 = []
        self.operator = operator
        self.channel = 0
        self.parent = parent
        self.overlay = []
        self.parent.MwaveLoadedData = []
        self.mode = mode
        self.protocol('WM_DELETE_WINDOW', self.close)

        monitors = get_monitors()
        indx = 0
        for i,monitor in enumerate(monitors):
            if ((monitor.x != 0) or (monitor.y != 0) ): indx = i

        w = monitors[indx].width
        h = monitors[indx].height
        x = monitors[indx].x
        y = monitors[indx].y
        self.geometry('%dx%d+%d+%d' % (w, h, x, y))

        self.initUI()

    def close(self):
        """
        Callback called when the user attempts to close the main window. If a run is
        still running, the attempt is denied.  If not, an "are you sure?" confirmation
        dialog is implemented.
        """
        if self.parent.operator.started:
            return
        else:
            keys, things = self.Match(self.parent.artists, 'mwave')
            while len(keys):
                xi = keys.pop(0)
                while xi in self.parent.artists: del self.parent.artists[xi]
            keys, things = self.Match(self.parent.widgets, 'mwave')
            while len(keys):
                xi = keys.pop(0)
                while xi in self.parent.widgets: del self.parent.widgets[xi]

            del self.parent.mwaveGUI
            self.destroy()

    def initUI(self):

        figwidth, figheight = 0.75 * self.winfo_screenwidth(), 0.75 * self.winfo_screenheight()
        # figreducedwidth = figwidth * 0.8
        fighalfheight = figheight * 0.5 - 50

        v = self.parent.operator.params._TraceLimitVolts

        ### UPPER NOTEBOOK
        uppernb = self.MakeNotebook(parent=self, name='UpperNB')
        uppernb.pack(side='top', fill='both', expand=1)

        ### UPPER TAB FRAME
        # tabframe = self.parent.widgets[self.mode + '_mwave_signal_tab'] = self.AddTab('Mwave', 'Current Signal', nbname='UpperNB')
        tabframe = self.widgets['mwave_signal_tab'] = self.AddTab('Mwave', 'Current Signal', nbname='UpperNB')

        if self.mode in ['ct', 'tt']:
            self.ProgressPanel('mwave_signal', success=False, parentmode=self.mode)
        else:
            self.ProgressPanel('mwave_signal', success=False)

        figure, widget, container = self.NewFigure(parent=tabframe, prefix='mwave', suffix='main', width=figwidth,
                                                   height=fighalfheight)

        ax1 = self.artists.axes_emg1_mwave = matplotlib.pyplot.subplot(1, 1, 1);
        minorLocator = AutoMinorLocator()

        ###LINE PLOTS
        self.parent.artists.tt_line_sigavg_mwave = self.parent.artists.ct_line_sigavg_mwave = self.parent.artists.rc_line_sigavg_mwave = \
        matplotlib.pyplot.plot((0, 0), (0, 0), color='k', linestyle='--')[0]
        self.parent.artists.tt_line_emg1_mwave = self.parent.artists.ct_line_emg1_mwave = self.parent.artists.rc_line_emg1_mwave = \
        matplotlib.pyplot.plot((0, 0), (0, 0), color=self.colors.emg1)[0]
        self.parent.artists.loaded_prevdata_mwave = matplotlib.pyplot.plot((0, 0), (0, 0), color='0.5', linewidth=1)[0]

        ###GRID AND TICKS
        ax1.grid(True);
        ax1.grid(True, which='minor', color='0.5', linestyle=':');
        ax1.tick_params(which='minor', length=4, color='0.75')
        ax1.xaxis.set_minor_locator(minorLocator);
        ax1.yaxis.set_minor_locator(minorLocator)
        ###AXIS CONTROLLER
        self.axiscontrollers_emg1.append(
            AxisController(ax1, 'y', units='V', start=(-v[0], +v[0]), narrowest=(-0.0001, +0.0001),
                           widest=(-20.000, +20.000)))
        self.widgets.yadjust_emg1 = PlusMinusTk(parent=tabframe, controllers=self.axiscontrollers_emg1).place(
            in_=widget, width=20, height=40, relx=0.93, rely=0.25,
            anchor='w')  # rely=0.75 for subplot( 2, 2, 4 ) only, or rely=0.25 for subplot( 2, 2, 2 ) only / both
        self.widgets.xadjust_emg1 = PlusMinusTk(parent=tabframe, controllers=[
            AxisController(ax, 'x', units='s', start=(-0.020, +0.100), narrowest=(-0.002, +0.010),
                           widest=(-0.100, +0.500)) for ax in self.MatchArtists('axes', 'mwave')]).place(in_=widget,
                                                                                                         width=40,
                                                                                                         height=20,
                                                                                                         relx=0.92,
                                                                                                         rely=0.05,
                                                                                                         anchor='se')  # rely=0.52 for subplot( 2, 2, 4 ) only, or rely=0.06 for subplot( 2, 2, 2 ) only / both

        ###FRAME FOR INFOITEMS
        self.frame = tkinter.Frame(tabframe, bg=self.colors.controls)
        self.parent.panel = self.panel = Bunch(
            MeanM=InfoItem('Mean M Amplitude:', 0, fmt='%.1f', units='V', color='#000000').tkc(self.frame, column=1),
            CurrentM=InfoItem('Current M Amplitude:', 0, fmt='%.1f', units='V', color='#000000').tkc(self.frame, column=3),
            LastM=InfoItem('Previous M Amplitude:', 0, fmt='%.1f', units='V', color='#000000').tkc(self.frame, column=5),
        )
        self.frame.grid_columnconfigure(4, weight=1)
        ###FRAME for the Response Overlay
        header = self.widgets.mwave_overlay_frame_header = tkinter.Frame(tabframe, bg=self.colors.progress)

        self.axes = self.artists.mwave_overlay_axes_main = figure.gca()
        responseInterval = self.parent.operator.params._ResponseStartMsec[self.channel] / 1000.0, \
                           self.parent.operator.params._ResponseEndMsec[self.channel] / 1000.0
        comparisonInterval = self.parent.operator.params._ComparisonStartMsec[self.channel] / 1000.0, \
                             self.parent.operator.params._ComparisonEndMsec[self.channel] / 1000.0
        prestimulusInterval = self.parent.operator.params._PrestimulusStartMsec[self.channel] / 1000.0, \
                              self.parent.operator.params._PrestimulusEndMsec[self.channel] / 1000.0
        self.overlay = ResponseOverlay(
            data=[], channel=self.channel,
            fs=self.parent.fs, lookback=self.parent.lookback,
            axes=self.axes, color=self.colors['emg%d' % (self.channel + 1)],
            responseInterval=responseInterval, comparisonInterval=comparisonInterval,
            prestimulusInterval=prestimulusInterval,
            updateCommand=self.Changed,
        )
        if len(self.axiscontrollers_emg1):
            self.overlay.yController.set(self.axiscontrollers_emg1[-1].get())
        else:
            self.overlay.yController.set([-v[0], v[0]])
        self.axiscontrollers_emg1.append(self.overlay.yController)

        ###SWITCH TO ENABLE OVERLAY
        self.switch = Switch(header, title='Change M/H Windows: ', offLabel='off', onLabel='on', initialValue=0,
                             command=self.EnableOverlay).pack(side='left', pady=3)
        ###OVERLAY BUTTON
        self.OverlayMwaveButton = self.parent.widgets.mwave_overlay_button_savetimings = tkinter.Button(header,
                                                                                                        text='Use marked timings',
                                                                                                        command=self.PersistTimings)
        ###A BUTTON TO LOAD PREVIOUS DATA M-WAVE
        self.LoadMwaveButton = self.parent.widgets.mwave_load_button = tkinter.Button(header, text='Load Previous Data',
                                                                                      command=self.LoadDataMwave)
        self.LoadMwaveButton.pack(side='left', pady=3, padx=10)
        ###PACK EVERYTHING
        tabframe.pack(side='left', padx=2, pady=2, fill='both', expand=1)
        header.pack(side='top', fill='both', expand=1)
        container.pack(side='top', fill='both', expand=True, padx=20, pady=5)
        self.frame.pack(side='bottom', expand=True, padx=50, pady=5)

        ###LOWER NOTEBOOK
        lowernb = self.MakeNotebook(parent=self, name='LowerNB')
        lowernb.pack(side='bottom', fill='both', expand=1)

        tabframe = self.widgets['mwave_sequence_tab'] = self.AddTab('Mwave', 'Sequence', nbname='LowerNB')

        figure, widget, container = self.NewFigure(parent=tabframe, prefix='sequence', suffix='main',
                                                   width=figwidth * 0.85, height=fighalfheight)
        figure.hold(True)
        ax2 = self.artists.axes_emg_seq_mwave = matplotlib.pyplot.subplot(1, 1, 1)
        self.axes_seq = figure.gca()

        self.parent.artists.sequenceM_line_mwave = \
        matplotlib.pyplot.plot((-1, -1), (0, 0), color=self.overlay.comparisonSelector.rectprops['facecolor'],
                               linestyle='', marker='^', markersize=10)[0]
        self.parent.artists.sequenceH_line_mwave = \
        matplotlib.pyplot.plot((-1, -1), (0, 0), color=self.overlay.responseSelector.rectprops['facecolor'],
                               linestyle='', marker='o', markersize=10)[0]

        if self.mode in 'rc': XaxisLimit = 40
        if self.mode in 'ct': XaxisLimit = int(getattr(self.parent.operator.params, '_' + 'ct' + 'TrialsCount'))
        if self.mode in 'tt': XaxisLimit = int(getattr(self.parent.operator.params, '_' + 'tt' + 'TrialsCount'))

        Xticks = range(1, XaxisLimit + 1)
        self.axes_seq.set_xlim([0.5, XaxisLimit + 0.5])
        self.axes_seq.set_xticks(Xticks)
        if XaxisLimit == 75: self.axes_seq.tick_params(axis='x', labelsize=8)
        ax2.grid(True)

        self.axiscontrollers_emg2.append(
            AxisController(ax2, 'y', units='V', start=(0, +v[0]), narrowest=(0, +0.0001), widest=(0, +10.000)))
        self.widgets.rc_yadjust_emg2 = PlusMinusTk(parent=tabframe, controllers=self.axiscontrollers_emg2).place(
            in_=widget, width=20, height=40, relx=0.93, rely=0.25, anchor='w')
        self.widgets.rc_yadjust_emg2.ChangeAxis(direction=+1)

        ###CREATE A SHADED REGION FOR MONITORING M-WAVE
        # widget = self.axes_seq.figure.canvas.get_tk_widget()
        frame = tkinter.Frame(tabframe, bg=tabframe['bg'])
        region_frame = tkinter.Frame(frame, bg=tabframe['bg'], borderwidth=1, relief='groove')

        # ,width=self.winfo_screenwidth()-figwidth-150,height=fighalfheight*0.85)
        # font = ('Helvetica', 12)
        fontBold = ('Helvetica', 11, 'bold')
        fontSMALL = ('Helvetica', 9)
        tkinter.Label(region_frame, text='M-Wave Overlay (mV)', font=fontBold, anchor='center',
                      bg=region_frame['bg']).pack(expand=1, fill='x', side='top', padx=5,
                                                  pady=5)  # .grid(row=0,columnspan=2,padx=5,pady=5,sticky='n')

        params = self.parent.operator.params

        # VARIABLES FOR DEFINING THE OVERLAY - TODO
        self.widgets.entry_meanVar = LabelledEntry(region_frame, 'Mean:', bg=region_frame['bg'], width=4).connect(
            params, '_MwaveOverlay', 0).pack(expand=1, padx=2,
                                             pady=1)  # .grid(row=1,columnspan=2,padx=1,pady=5,sticky='w')
        self.widgets.entry_percVar = LabelledEntry(region_frame, '+/- %:', bg=region_frame['bg'], width=3).connect(
            params, '_MwaveOverlay', 1).pack(expand=1, padx=2,
                                             pady=1)  # .grid(row=1,columnspan=2,padx=1,pady=5,sticky='e')

        self.region_frame_button = tkinter.Button(region_frame, text='Update Overlay', font=fontSMALL,
                                                  command=self.RegionUpdate, width=12).pack(expand=1, padx=2,
                                                                                            pady=5)  # .grid(row=3,columnspan=2,padx=5,pady=5)

        self.CheckVar = tkinter.IntVar()
        self.CheckButton = tkinter.Checkbutton(region_frame, text='Loaded Data', font=fontSMALL, variable=self.CheckVar,
                                               command=self.RegionUpdate, bg=region_frame['bg'], selectcolor='white')
        self.CheckButton.pack(expand=1, side='bottom', padx=2,
                              pady=5)  # .grid(row=4,columnspan=2,padx=5,pady=5,sticky='esw')

        self.RegionFrameAxes = figure.gca()

        low = float(params._MwaveOverlay[0] * (1 - params._MwaveOverlay[1] / 100))
        high = float(params._MwaveOverlay[0] * (1 + params._MwaveOverlay[1] / 100))

        self.axes_seq.set_ylim([0, high / 1000])
        self.widgets.rc_yadjust_emg2.ChangeAxis(direction=+1)

        self.axhspan = self.RegionFrameAxes.axhspan(low / 1000, high / 1000, alpha=0.1, color='green')
        self.axhline = self.RegionFrameAxes.axhline(float(params._MwaveOverlay[0]) / 1000, 0, 1, linestyle='--',
                                                    color='green')

        self.RegionUpdate()

        tabframe.pack(side='left', fill='both', expand=1, padx=5, pady=5)
        container.pack(side='left', fill='both', expand=1, padx=5, pady=5)
        frame.pack(side='right', fill='both', expand=1, padx=5, pady=5)
        region_frame.place(rely=0.5, relx=0.5, anchor='center')

        self.update();
        self.geometry(
            self.geometry())  # prevents Tkinter from resizing the GUI when component parts try to change size (STEP 18 from http://sebsauvage.net/python/gui/ )
        # self.resizable(False, False)
        self.latest = None
        self.CheckUpdate()
        self.wm_state('zoomed')  # maximize the window

    def RegionUpdate(self):

        # Check if we have loaded data and if checkbox checked

        if (self.CheckVar.get()) and (len(self.parent.MwaveLoadedData)):

            self.widgets.entry_meanVar.entry.config(state='disabled')
            self.widgets.entry_percVar.entry.config(state='disabled')

            ind1 = float(self.parent.operator.params._ComparisonStartMsec[self.channel]) / 1000
            ind2 = float(self.parent.operator.params._ComparisonEndMsec[self.channel]) / 1000

            MwaveMagOverlay = ResponseMagnitudes(data=self.parent.MwaveLoadedData, channel=1, interval=(ind1, ind2),
                                                 fs=self.LoadedDatafs, lookback=self.LoadedDataLookback, p2p=False,
                                                 SingleTrial=True)
            self.axhspan.remove()
            self.axhline.remove()

            var1 = MwaveMagOverlay - MwaveMagOverlay * 0.2
            var2 = MwaveMagOverlay + MwaveMagOverlay * 0.2

            self.axhspan = self.RegionFrameAxes.axhspan(var1, var2, alpha=0.3, color='green')
            self.axhline = self.RegionFrameAxes.axhline(MwaveMagOverlay, 0, 1, linestyle='--', color='green')
            self.axes_seq.set_ylim([0, var2])
            self.widgets.rc_yadjust_emg2.ChangeAxis(direction=+1)

            self.widgets.entry_minVar.entry['text'] = str(var1)

            self.RegionFrameAxes.figure.canvas.draw()

        elif (self.CheckVar.get()):
            self.CheckVar.set(0)
        else:

            self.widgets.entry_meanVar.entry.config(state='normal')
            self.widgets.entry_percVar.entry.config(state='normal')

            self.CheckVar.set(0)

            var1 = self.ValidateEntry(self.widgets.entry_meanVar.entry.get())
            var2 = self.ValidateEntry(self.widgets.entry_percVar.entry.get())

            if ((var1 != None) and (var2 != None)):

                if (var2 <= 100) and (var2 > 0):
                    self.widgets.entry_meanVar.entry.config(bg='white')
                    self.widgets.entry_percVar.entry.config(bg='white')

                    if ((var1 < 1) and (var1 != 0)): var1 = var1 * 1000

                    self.axhspan.remove()
                    self.axhline.remove()

                    low = float(var1 * (1 - var2 / 100))
                    high = float(var1 * (1 + var2 / 100))

                    self.axhspan = self.RegionFrameAxes.axhspan(low / 1000, high / 1000, alpha=0.3, color='green')
                    self.axhline = self.RegionFrameAxes.axhline(var1 / 1000, 0, 1, linestyle='--', color='green')
                    self.axes_seq.set_ylim([0, high / 1000])
                    self.widgets.rc_yadjust_emg2.ChangeAxis(direction=+1)

                    self.RegionFrameAxes.figure.canvas.draw()
                else:
                    self.widgets.entry_percVar.entry.config(bg='red')
            else:

                if var1 == None: self.widgets.entry_meanVar.entry.config(bg='red')
                if var2 == None: self.widgets.entry_percVar.entry.config(bg='red')

        self.apply()

        return False

    def apply(self):
        changed = Bunch()
        for key, widget in self.widgets.items():
            if isinstance(widget, ConnectedWidget):
                widget.push(changed)
        for k, v in sorted(changed.items()):
            if v: self.parent.Log('Changed setting %s to %s' % (k.strip('_'), repr(self.parent.operator.params[k])))
        if True in changed.values(): self.parent.operator.needSetConfig = True

    def ValidateEntry(self, value):
        try:
            if value:
                v = float(value)
                return v
        except:
            return None

    def TimingsSaved(self):
        """
        Check whether the timings (i.e. endpoints of the prestimulus, reference and target
        response interval selectors) have been remembered (stored in self.parent.operator.params)
        by pressing the "Use Marked Timings" button. Return True or False accordingly.
        """
        result = True
        params = self.parent.operator.params

        def equal(a, b):
            return float('%g' % a) == float('%g' % b)

        if self.overlay.responseSelector:
            start, end = [sec * 1000.0 for sec in self.overlay.responseSelector.get()]
            if not equal(params._ResponseStartMsec[0], start) or not equal(params._ResponseEndMsec[0],
                                                                           end): result = False
        if self.overlay.comparisonSelector:
            start, end = [sec * 1000.0 for sec in self.overlay.comparisonSelector.get()]
            if not equal(params._ComparisonStartMsec[0], start) or not equal(params._ComparisonEndMsec[0],
                                                                             end): result = False
        if self.overlay.prestimulusSelector:
            start, end = [sec * 1000.0 for sec in self.overlay.prestimulusSelector.get()]
            if not equal(params._PrestimulusStartMsec[0], start) or not equal(params._PrestimulusEndMsec[0],
                                                                              end): result = False
        return result

    def LoadDataMwave(self):

        if len(self.parent.MwaveLoadedData):
            self.parent.MwaveLoadedData = [0, 0]
            self.parent.MwaveFigureFlag = 3
            self.parent.NewTrial(self.parent.MwaveLoadedData, store=False)
            self.parent.MwaveFigureFlag = 0
            self.LoadMwaveButton.config(text='Load Previous Data')
            self.parent.MwaveLoadedData = []
        else:

            self.initialdir = self.parent.operator.DataRoot()

            self.LoadedDatafs = 0
            self.LoadedDataLookback = 0
            self.LoadedData = []
            self.LoadedApplicationMode = ''

            self.OpenFiles()
            NumTrials = len(self.LoadedData)

            LoadedSignal = []

            if self.LoadedApplicationMode in ['ct', 'tt']:
                for trials in range(0, NumTrials):
                    if trials == 0:
                        LoadedSignal = self.LoadedData[trials][self.channel]
                    else:
                        for x, y in enumerate(self.LoadedData[trials][self.channel]):
                            LoadedSignal[x] += y
                            LoadedSignal[x] /= 2
            if self.LoadedApplicationMode == 'rc':
                LoadedSignal = DetermineRCPoint(parent=self, ntrials=NumTrials, data=self.LoadedData,
                                                channel=self.channel).Avg

            if len(LoadedSignal):
                self.parent.MwaveLoadedData = [TimeBase(LoadedSignal, self.LoadedDatafs, self.LoadedDataLookback),
                                               LoadedSignal]
                self.parent.MwaveFigureFlag = 3
                self.parent.NewTrial(self.parent.MwaveLoadedData, store=False)
                self.parent.MwaveFigureFlag = 0

                self.LoadMwaveButton.config(text='Clear Data')

        return False

    def UpdateResults(self, *unused_args):

        if hasattr(self, 'overlay'):
            self.overlay.Update()
            if self.TimingsSaved():
                self.parent.widgets.mwave_overlay_button_savetimings.configure(state='disabled', bg=self.colors.button)
            else:
                self.parent.widgets.mwave_overlay_button_savetimings.configure(state='normal', bg='#FF4444')
        ax = self.artists.get('mwave_overlay_axes_main', None)
        if ax: matplotlib.pyplot.figure(ax.number).sca(ax)
        self.DrawFigures()

    def PersistTimings(self):
        """
        Store timing information from the ResponseOverlay object self.overlay.  This
        information consists of the endpoints of the prestimulus, reference and target
        response interval selectors. Store them in self.parent.operator.params
        This is called when the "Use Marked Timings" button is pressed.
        """
        if self.switch.get() and not self.parent.operator.started:
            if self.overlay.prestimulusSelector:
                start, end = [sec * 1000.0 for sec in self.overlay.prestimulusSelector.get()]
                self.parent.operator.Set(_PrestimulusStartMsec=[start, start], _PrestimulusEndMsec=[end, end])
                self.parent.Log('Updated pre-stimulus interval: %g to %g msec' % (start, end))
            if self.overlay.comparisonSelector:
                start, end = [sec * 1000.0 for sec in self.overlay.comparisonSelector.get()]
                self.parent.operator.Set(_ComparisonStartMsec=[start, start], _ComparisonEndMsec=[end, end])
                self.parent.Log('Updated reference response interval: %g to %g msec' % (start, end))
            if self.overlay.responseSelector:
                start, end = [sec * 1000.0 for sec in self.overlay.responseSelector.get()]
                self.parent.operator.Set(_ResponseStartMsec=[start, start], _ResponseEndMsec=[end, end])
                self.parent.Log('Updated target response interval: %g to %g msec' % (start, end))
            self.UpdateResults()

    def EnableOverlay(self, rectified=False):

        if self.switch.get():
            self.overlay.comparisonSelector.rect.set_visible(True)
            self.overlay.comparisonSelector.mintext.set_visible(True)
            self.overlay.comparisonSelector.maxtext.set_visible(True)

            self.overlay.responseSelector.rect.set_visible(True)
            self.overlay.responseSelector.mintext.set_visible(True)
            self.overlay.responseSelector.maxtext.set_visible(True)

            self.overlay.prestimulusSelector.rect.set_visible(True)
            self.overlay.prestimulusSelector.mintext.set_visible(True)
            self.overlay.prestimulusSelector.maxtext.set_visible(True)
            self.OverlayMwaveButton.pack(side='left', pady=3)
            self.overlay.Update()
            self.DrawFigures()
        else:
            self.overlay.comparisonSelector.rect.set_visible(False)
            self.overlay.comparisonSelector.mintext.set_visible(False)
            self.overlay.comparisonSelector.maxtext.set_visible(False)

            self.overlay.responseSelector.rect.set_visible(False)
            self.overlay.responseSelector.mintext.set_visible(False)
            self.overlay.responseSelector.maxtext.set_visible(False)

            self.overlay.prestimulusSelector.rect.set_visible(False)
            self.overlay.prestimulusSelector.mintext.set_visible(False)
            self.overlay.prestimulusSelector.maxtext.set_visible(False)
            self.OverlayMwaveButton.pack_forget()
            self.overlay.Update()
            self.DrawFigures()

    def Changed(self, *pargs):
        """
        Flag that something has changed and needs updating
        """
        self.latest = time.time()

    def CheckUpdate(self):
        """
        Check every 100 msec: if there is new activity flagged by Changed(), and the latest
        activity occurred more than 2s ago, then call UpdateResults().
        This function renews its own schedule using Tk.after().  The initial scheduling
        is done by an explicit call to CheckUpdate() in body()
        """
        if self.latest != None and time.time() - self.latest > 0.5: self.UpdateResults(); self.latest = None
        self.after_id = self.parent.after(100, self.CheckUpdate)

    def ListDatFiles(self):
        return sorted(glob.glob(os.path.join(self.operator.DataDirectory(), '*.dat')))

    def ReadDatFile(self, filename, **kwargs):
        from BCPy2000.BCI2000Tools.Chain import bci2000root, bci2000chain  # also imports BCI2000Tools.Parameters as a central component and SigTools for a few things

        if bci2000root() == None:
            bci2000root(os.path.join(BCI2000LAUNCHDIR, '..'))
        filename = TryFilePath(filename, os.path.join(self.parent.operator.DataDirectory(), filename))

        s = bci2000chain(filename, 'IIRBandpass', **kwargs)
        try:
            trigIndex = s.Parms.ChannelNames.Value.index(s.Parms.TriggerChannel.Value)
        except ValueError:
            trigIndex = s.Parms.TriggerChannel.NumericValue - 1
        p = s.ImportantParameters = Bunch(
            LookBack=s.Parms.LookBack.ScaledValue / 1000.0,
            LookForward=s.Parms.LookForward.ScaledValue / 1000.0,
            SamplingRate=s.Parms.SamplingRate.ScaledValue,
            SubjectName=s.Parms.SubjectName.Value,
            ApplicationMode=s.Parms.ApplicationMode.Value.lower(),
        )

        try:
            import \
                BCPy2000.SigTools.NumTools as NumTools  # TODO: it would be nice to use the TrapFilter as a command-line filter as well, instead of the NumTools code (edges, epochs, refrac and diffx are needed). But for now BCI2000 framework bugs prevent this (or at least make it impossibly difficult to debug the problems I have observed if they really arise from TrapFilter itself)
        except ImportError:
            import \
                NumTools  # py2exe fallback: the file for BCPy2000.SigTools.NumTools will be included by hand but the rest of BCPy2000.SigTools will be excluded
        s.Epochs = s.__class__()
        # In FullMonty-based operation using epocs.py, scipy will be available, so BCI2000Tools.Chain will successfully import SigTools,
        # so the container class will be a SigTools.sstruct and the above command will be unnecessary.   By contrast, in the py2exe-made
        # version, scipy and SigTools will be excluded. Later versions of BCI2000Tools (bci2000.org r4734 and up) are sensitive to this
        # possibility, and fall back on the lighter-weight code in BCI2000Tools.LoadStream2Mat, where our Bunch() class is replicated -
        # in this case, the line above is necessary to initialize the empty substruct container.
        edgeIndices = NumTools.edges(s.Signal[:, trigIndex] >= s.Parms.TriggerThreshold.ScaledValue)
        s.Epochs.Data, s.Epochs.Time, s.Epochs.Indices = NumTools.epochs(s.Signal / 1e6, edgeIndices,
                                                                         length=p.LookForward + p.LookBack,
                                                                         offset=-p.LookBack, refractory=0.5,
                                                                         fs=p.SamplingRate, axis=0, return_array=True)
        if len(s.Epochs.Data): s.Epochs.Data = list(
            s.Epochs.Data.transpose(0, 2, 1))  # AnalysisWindow and its subplots will expect trials by channels by time
        return s

    def OpenFiles(self, filenames=None, **kwargs):  ###AMIR Taken from offline analysis

        if filenames == None:
            import tkFileDialog

            filenames = tkFileDialog.askopenfilenames(parent=self, initialdir=self.initialdir,
                                                      title="Select one or more data files",
                                                      filetypes=[("BCI2000 .dat file", ".dat")])

            if isinstance(filenames,
                          basestring):  # you suck, tkFileDialog.askopenfilenames, for changing your output format from an easy-to-use tuple in Python 2.5 to an impossibly awkward single string in later versions
                joined = filenames
                filenames = []
                while len(joined):
                    m = re.match(r'\{(.+?)\}', joined)
                    if m: filenames.append(m.group().strip('{}')); joined = joined[m.end():].strip(); continue
                    m = re.match(r'(\S+?)\s+', joined + ' ')
                    if m: filenames.append(m.group().strip()); joined = joined[m.end():].strip(); continue
                    joined = joined.strip()
            # look how many lines of annoying difficult-to-debug crap you made me write.
            filenames = sorted(filenames)
        if not filenames: return
        objs = [self.ReadDatFile(filename, **kwargs) for filename in filenames]
        objs = [obj for obj in objs if len(obj.Epochs.Data)]  # TODO: seems to exclude VC files
        if len(objs) == 0:
            import tkMessageBox
            tkMessageBox.showerror("EPOCS Offline Analysis",
                                   '\n   '.join(["No trials found after scanning the following:"] + filenames))
            return

        self.initialdir = os.path.split(filenames[0])[0]
        first = objs[0].ImportantParameters
        unique = Bunch([(field, sorted(set([obj.ImportantParameters[field] for obj in objs]))) for field in first])
        errs = []
        for field in 'LookBack LookForward SamplingRate'.split():
            vals = unique[field]
            if len(vals) > 1: errs.append("%s setting differs between runs (values %s)" % (field, repr(vals)))
        if len(errs): raise ValueError(
            '\n   '.join(["runs are incompatible unless you explicitly override the following:"] + errs))

        ###CHANGE THIS TO CHECK IT IS THE SAME SUBJECT AS WHAT I AM CURRENTLY STUDYING
        if len(unique.SubjectName) == 1:
            if unique.SubjectName[0] != self.parent.operator.params.SubjectName:
                import tkMessageBox
                if not tkMessageBox.askyesno('SubjectDiffers',
                                             'Warning: subject (%s) you are loading is not the same as the current one, continue anyway?' %
                                                     unique.SubjectName[0], parent=self, ):
                    return

        self.LoadedDatafs = float(unique.SamplingRate[0])
        self.LoadedDataLookback = float(unique.LookBack[0])
        self.LoadedData = reduce(list.__add__, [obj.Epochs.Data for obj in objs])
        self.LoadedApplicationMode = unique.ApplicationMode[0]

        return