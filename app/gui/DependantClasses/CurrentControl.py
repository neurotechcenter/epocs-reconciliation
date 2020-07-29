import Tkinter as tkinter
import numpy as np
from collections import OrderedDict
from CoreGUIcomponents import Switch

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

class CurrentControlWindow(tkinter.Toplevel):
    """
    ###AMIR
    An M Wave Analysis Window is created when the "M-Wave Analysis" button is
    pressed on the ct tab of the GUI().
    """
    def __init__(self, parent,automate=False):

        tkinter.Toplevel.__init__(self)
        if int(parent.operator.remote.GetParameter('EnableDS8ControlFilter')) == 1: self.wm_title('DS8 Current Stimulation Control')
        else: self.wm_title('DS5 Current Stimulation Control')
        #self.wm_geometry('225x150')
        self.wm_resizable(width=False,height=False)
        self.wm_attributes("-topmost",1)
        self.withdraw()
        self.parent = parent
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.CurrentAmplitude = 0
        self.StimLocations = OrderedDict()#Bunch()
        self.CurrentLimit = self.parent.operator.params._CurrentLimit
        self.AutomateEnabled = automate

        #self.StimLocations['Location1'] = 0.0 #To hold the threshold value for each location
        #self.CurrentAmplitudeState = [] #historical of the currents used
        self.CurrentAmplitudeState = Bunch(st=[], vc=[], rc=[], ct=[], tt=[])
        self.STDataStorage = []
        self.widgets = Bunch()

        #self.RCStorage = Bunch(data=[], currents=[], stimpool=[], run=[], log=[], optcurrent=[], use=[], grad=[],Min=[],Max=[],Mtarget=[],nTrials=[],Mwin=[],Hwin=[])
        if self.parent.mode not in ['offline']: self.initUI()

    def initUI(self):

        self.fontLARGE = ('Helvetica', 32)
        fontMED = ('Helvetica', 15)
        fontSMALL = ('Helvetica', 12)

        #Main Header
        header = tkinter.Frame(self,bg='white')

        #Frame for CurrentLabel
        self.widgets.frame_currentlabel = w = tkinter.LabelFrame(header,bg='white',padx=5,pady=5) #width=10,height=12
        w.grid(row=0, column=0, columnspan=2, rowspan=2, padx=5, pady=5, sticky='nsew')
        w.grid_columnconfigure(0, weight=1)
        w.grid_rowconfigure(0, weight=1)
        #Current Label
        self.currentlabeltxt = tkinter.StringVar()
        self.currentlabel = tkinter.Label(w, font=self.fontLARGE, textvariable=self.currentlabeltxt,bg='white',fg='red',width=8)
        Val = float(self.GetCurrent())
        LabelTxt = str(Val)+'mA'
        self.currentlabeltxt.set(LabelTxt)
        self.currentlabel.pack(expand=1,fill='both') #grid(row=0, column=0, columnspan=2,rowspan=2, padx=10, pady=5, sticky='w')

        #Frame for Buttons
        self.widgets.frame_buttons = w = tkinter.LabelFrame(header, bg='white', padx=5,pady=5)  # width=10,height=12
        w.grid(row=0, column=2, columnspan=1, rowspan=2, padx=5, pady=5, sticky='nsew')
        #w.bind('<Configure>', self.resize)
        w.grid_columnconfigure(0, weight=1)
        w.grid_rowconfigure(0, weight=1)

        #Buttons - UP/DOWN
        self.upButton = tkinter.Button(w, text='UP', command= lambda: self.Increment(val=1), font=fontMED,width=6)
        self.downButton = tkinter.Button(w, text='DOWN', command= lambda: self.Increment(val=-1), font=fontMED,width=6)
        self.upButton.pack(side='top',expand=1,pady=3)#grid(row=0, column=2, columnspan=1,rowspan=1, padx=10, pady=5, sticky='nsew')
        self.downButton.pack(side='top',expand=1,pady=3)#grid(row=1, column=2, columnspan=1,rowspan=1, padx=10, pady=5, sticky='nsew')

        #Frame for Increment Label/Text
        self.widgets.frame_increment = w = tkinter.LabelFrame(header, bg='white', padx=5, pady=5)  # width=10,height=12
        w.grid(row=2, column=0, columnspan=3, rowspan=1, padx=5, pady=5, sticky='nsew')
        #w.bind('<Configure>', self.resize)
        w.grid_columnconfigure(0, weight=1)
        w.grid_rowconfigure(0, weight=1)
        #Increment Label/Text
        self.incrementtxt = tkinter.StringVar()
        self.incrementtxt.set(str(self.parent.operator.params._IncrementStart))
        self.incrementlabel = tkinter.Spinbox(w,font=fontMED,from_=0,increment=self.parent.operator.params._IncrementIncrement,to=5,bg='white',format="%02.3f",width=5,textvariable=self.incrementtxt,command=self.IncrementStep)
        self.incrementlabel.pack(side='left')#grid(row=2, column=0, columnspan=1, padx=3, pady=5, sticky='nsew')
        #self.incrementtxt.trace('w', self.CheckValue)
        self.incrementlabel.config(state='readonly')

        self.label2 = tkinter.Label(w, font=fontMED, text='mA',bg='white',width=3)
        self.label2.pack(side='left')#grid(row=2, column=1, padx=0, pady=5, sticky='nsew')

        self.switch_limb = Switch(w, title='Limb:    ', offLabel='Left', onLabel='Right',
                                               values=['left', 'right'], command=self.SwitchLegs, initialValue=self.parent.operator.params._Limb).connect(self.parent.operator.params,'_Limb').pack(side='left', padx=10, pady=10)


        self.Automate = tkinter.IntVar()
        self.AutomateCheck = tkinter.Checkbutton(w, text='Automate', var=self.Automate, bg='white',borderwidth=0.5, selectcolor='white', font=fontMED,command=self.AutomateCheckFunc)
        if self.AutomateEnabled: self.AutomateCheck.pack(side='right')  # grid(row=2, column=2, padx=3, pady=5, sticky='nsew')
        if self.parent.operator.params._DigitimerEnable == 'off': self.AutomateCheck.config(state='disabled')

        header.grid_columnconfigure(0, weight=1)
        header.grid_rowconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=1)
        header.grid_rowconfigure(1, weight=1)
        header.grid_columnconfigure(2, weight=1)
        header.grid_rowconfigure(2, weight=1)

        header.pack(side='top', fill='both', expand=1)

    def IncrementStep(self):

        #If we are automating the recruitment curve and in manual mode... lets update delta in CurrentControl
        if self.AutomateEnabled and self.Automate.get()==1 and self.parent.mode in ['rc'] and self.parent.operator.params._RCendpoint=='Manual':
            if hasattr(self.parent,'ControlObject'):
                #CurrentDelta = self.parent.ControlObject.Delta
                #CurrentAmplitude = self.parent.ControlObject.CurrentAmplitude
                self.parent.ControlObject.Delta = int(float(self.incrementtxt.get())*1000)
                #TODO: Should Delta change also affect the next current (which has already been set?)
                #self.parent.ControlObject.CurrentAmplitude = CurrentAmplitude + ()


    def AutomateCheckFunc(self):
        """
        For Stimulus test mode, if we are perfoming automated H-reflex threshold detection then we enable the analysis window in this mode
        """
        return
        #this is for a later release
        #if self.Automate.get() == 1:
        #    EnableWidget(self.parent.MatchWidgets('st','analysis'), True)
        #else:
        #    EnableWidget(self.parent.MatchWidgets('st', 'analysis'), False)


    def SwitchLegs(self,*unused_args):



        if self.parent.operator.params._Limb != self.switch_limb.get():
            #D188 1 is right, 2 is left


            self.parent.operator.params._Limb = self.switch_limb.get()

            t = tkinter.Toplevel(bg='white')
            g = self.geometry()

            w = int(g.split('x')[0]); h = int(g.split('+')[0].split("x")[1])
            x = int(g.split('+')[1]); y = int(g.split('+')[2])

            t.geometry('%dx%d+%d+%d' % (150, 85, x + (w-150)/2, y + (y-85)/2))
            t.wm_attributes("-topmost", 1)
            t.title("Limbs")
            tkinter.Message(t,text="Switching Legs...",bg='white',padx=20,pady=20).pack()
            t.update()
            self.parent.SetupEMGChannels()
            #self.parent.SetBarLimits('vc', 'rc', 'ct', 'tt')
            if hasattr(self.parent, 'mwaveGUI'):
                self.parent.mwaveGUI.EnableOverlay()
            t.destroy()




    def resize(self, event):
        return
        #self.font = tkFont.Font(size=int(event.height/3))
        #self.currentlabel.config(font=tkFont.Font(size=int(event.height/3)))

    def CheckValue(self,val,val2,val3):

        #if the increment value is manually changed then make sure it is between 0 and 5mA, and is actually a number
        if (self.incrementtxt.get() != ''):
            try:
                v = float(self.incrementtxt.get())
                if (v<0): self.incrementtxt.set('0.00')
                elif (v>5): self.incrementtxt.set('5.00')
                else: self.incrementtxt.set(v)
            except:
                self.incrementtxt.set('0.5')
                #tkMessageBox.showerror ("Current Error","Incorrect increment value inputed please correct, must be between 0-5mA")

    def GetCurrent(self,mode=None):

        #State CurrentAmplitude is a 16bit state that also requires knowledge of the Analog Output Range (default +/-5V)
        #So The voltage we send out on the NIDAQ = AORange*Value(CurrentAmplitude)/(2^16 - 1)
        #For the DS5 this is a 5V=50mA mapping

        #Check if the system has started running or at least preflight
        if self.parent.operator.started:
            #Extract current amplitude from State CurrentAmplitude if we Running == 1
            StateAmplitude = self.parent.states[mode].CurrentAmplitude
            CurrentAmplitudemA = float(StateAmplitude)/1000 #mA
            #Update the label and our local-global variable
            self.CurrentAmplitude = StateAmplitude
            self.SetLabel(value=CurrentAmplitudemA)

            return CurrentAmplitudemA

        elif (self.parent.operator.needSetConfig):
            StateAmplitude = float(self.parent.operator.remote.GetParameter('InitialCurrent'))
            self.CurrentAmplitude = float(StateAmplitude)*1000
            self.SetLabel(StateAmplitude)
            return StateAmplitude
            #Try to extract it from current states
        else:
            return self.CurrentAmplitude

    def SetLabel(self,value):
        if abs(value) > 50: value=float(value)/1000
        LabelTxt = "%.2f" % value#str(value) + 'mA'
        self.currentlabeltxt.set(LabelTxt + 'mA')

    def Increment(self,val):

        #When first loaded, we have not done a preflight so adjusting the value will not have an effect yet
        #Read Increment Value
        #if not self.CheckValue(val=self.incrementlabel.get()): return
        if (self.Automate.get() == 1) and (self.parent.operator.started and not(self.parent.operator.params._RCendpoint == 'Manual')): return  # cannot increment when automated unless manual selected
        IncrementValue = float(self.incrementlabel.get())
        #Read Current Value
        CurrentVal = float(self.CurrentAmplitude)/1000 #in mA

        if (val == 1):
            NewVal = CurrentVal+IncrementValue
        else:
            NewVal = CurrentVal - IncrementValue

        if (NewVal < 0 ): NewVal = 0
        if (NewVal > self.CurrentLimit): NewVal = self.CurrentLimit

        self.SetNewCurrent(value=NewVal)
        #if not (self.parent.operator.started):
        self.currentlabeltxt.set(str(NewVal)+'mA')
        self.CurrentAmplitude = NewVal*1000

        if (self.Automate.get() == 1) and  (self.parent.operator.params._RCendpoint == 'Manual'):
            if hasattr(self.parent,'ControlObject'): self.parent.ControlObject.CurrentAmplitude = self.CurrentAmplitude

        
        return

    def SetNewCurrent(self,value):
        #value input as current
        if abs(value) > 50: value = float(value)/1000
        Value2set = (np.uint16)(value*1000)

        #If not started or it exists (as in running has been 1, then we change current amplitude
        self.parent.operator.bci2000('Set State CurrentAmplitude ' + str(Value2set))
        self.parent.operator.bci2000('Set State NeedsUpdating 1')

        if not (self.parent.operator.started):     #Not started before
            self.parent.operator.bci2000('Set Parameter InitialCurrent ' + str(value))
            self.parent.operator.needSetConfig = True
        self.CurrentAmplitude = Value2set

    def addLocation(self,value=0):
        n = len(self.StimLocations)
        val = 'Location'+str(n)
        self.StimLocations[val] = value

    def close(self):
        if self.parent.operator.started: return
        else: self.withdraw()
