#FUNCTIONS RELATED TO AUTOMATION

import Tkinter as tkinter
import tkMessageBox
import numpy, time
from ..CoreFunctions import Bunch
from ..CoreGUIcomponents import Dialog, OptionsDialog
from collections import OrderedDict
import csv # used for loading PID configure file
import sys # for testing

class CurrentControl(object):
    """
    A control class for controlling the current for different modes.

    """

    def __init__(self,parent,mode,EndPoint='Mmax',RCindex=None):

        """
        Initialize the parent and mode we are in (there are mode specific parameters)
        :param parent: is the main GUI interface
        :param mode: ST, RC, CT or TT
        :param Hmax: In building an RC we can choose just to go to Hmax, otherwise Mmax.
        :param RCindex: In CT and TT mode this tell us which RC (if multipe) to use the parameters of RCStorage.
        """
        self.parent = parent
        self.mode = mode
        self.states = self.parent.states
        self.channel = 0  # EMG1

        self.minDelta = 0.25 #minimum delta (resolution) to allow the system to go to

        #Add the extra expression so that
        self.parent.operator.bci2000("set parameter TriggerExpression StimulationControl")

        if self.mode in ['st']:
            self.ResponseCurrent = 0 #When a response is found this is where it is stored for ST
            self.ResponseAmplitude = 0
            self.PrevResponseFound = False
            self.ResponseFound = False
            self.CurrentAmplitude = 3 #float(self.parent.operator.remote.GetParameter('InitialCurrent'))
            self.CurrentLimit = self.parent.operator.params._CurrentLimit #mA #TODO vary for different muscle groups
            self.Delta = 2.0 #Delta is the current step that the control takes when incrementing/decrementing current. Default at 1mA.
            self.H = []
            #If we are using the D188 we need to control the sequence of events that occur here.
            #First, we will start with location 4, and move from there.
            self.D188ControlEnabled = False
            self.D188Control = None

        elif self.mode in ['rc']:
            self.CurrentLimit = self.parent.operator.params._CurrentLimit   # mA
            self.GoBack = 0; self.GoBackCurrent = []
            delta = self.parent.operator.params._aDelta
            self.Delta = int(delta*1000) #0.5  # Delta is the current step that the control takes when incrementing/decrementing current. Default at 1mA.
            self.parent.stimGUI.incrementtxt.set(str(delta))
            self.CurrentAmplitude = float(self.parent.stimGUI.CurrentAmplitude)
            self.Pooling = int(self.parent.operator.params._aPooling) ; self.PoolingIndex = 0; self.HPooledValues = []; self.MPooledValues = []; self.BGPooledValues = []#Average each 4 values, Pooling index logs how many i or 4 we have to know when to average
            self.AddingCurrentsState = False; self.AdditionalCurrentIndx = 0 #A state that we go into if we need more currents between Hthreshold and Hmax
            self.HmaxReached = False; self.MmaxReached = False #States to check where we are...
            self.HmaxCurrent = 0
            self.EndPoint = EndPoint
        elif self.mode in ['ct','tt']:	
            with open('.\configPID.csv') as csvfile:
                spamreader = csv.reader(csvfile,delimiter=',')
                next(spamreader)				
                for row in spamreader:
                    Setpoint = numpy.fromstring(row[0],dtype=float,sep=' ')
                    InitialCurrent = numpy.fromstring(row[1],dtype=float,sep=' ')
                    gainP = numpy.fromstring(row[2],dtype=float,sep=' ')
                    gainI = numpy.fromstring(row[3],dtype=float,sep=' ')
                    gainD = numpy.fromstring(row[4],dtype=float,sep=' ')					
                    self.CurrentLimit = numpy.fromstring(row[5],dtype=float,sep=' ')	
                    self.CurrentRange = (0,numpy.fromstring(row[5],dtype=float,sep=' '))					
            self.Method = 'H'#self.parent.operator.params._ControlMethod			
            #Range we can work with
            if 'H' in self.Method:
                #self.h = StimControl(Setpoint=self.parent.stimGUI.RCStorage['Mtarget'][RCindex],Gradient=self.parent.stimGUI.RCStorage['grad'][RCindex],N=3)
                self.h = StimControl(Setpoint=120,Gradient=0,N=3,InitialCurrent,gainP,gainI,gainD)
            #self.CurrentTarget =  self.parent.stimGUI.RCStorage['optcurrent'][RCindex]
            self.CurrentTarget =  float(self.parent.stimGUI.CurrentAmplitude)
            #self.CurrentAmplitude = self.parent.stimGUI.RCStorage['optcurrent'][RCindex]
            self.CurrentAmplitude = float(self.parent.stimGUI.CurrentAmplitude)					
            #self.CurrentRange = (self.parent.stimGUI.RCStorage['Min'][RCindex],self.parent.stimGUI.RCStorage['Max'][RCindex])
        self.ProcessCompleted = False  # tells us to stop...

        #Assuming when initialized we will set the amplitude and run the process at each increment of the TrialCounter
        #self.parent.stimGUI.SetNewCurrent(value=self.CurrentAmplitude)
        #self.parent.stimGUI.SetLabel(value=self.CurrentAmplitude)
        #self.parent.stimGUI.CurrentAmplitudeState = []
        #self.parent.stimGUI.CurrentAmplitudeState.append(self.CurrentAmplitude)
        self.InitializeGlobalaIndices()

    def InitializeGlobalaIndices(self):
        """
        For sake of accurately extracting H, M and BG info, we extract the indices of the signal from the params.

        The H, M and BG are not always computed for every channel, so this saves having to re-initialize the indices.
        """

        Lookback = self.parent.lookback
        Fs = self.parent.fs

        self.BGind = []
        self.BGind.append( int(round( ((float(self.parent.operator.params._PrestimulusStartMsec[self.channel]) / 1000)+Lookback)*Fs) ) )
        self.BGind.append( int(round( ((float(self.parent.operator.params._PrestimulusEndMsec[self.channel]) / 1000) + Lookback)*Fs) ) )

        self.Hind = []
        self.Hind.append( int(round( ((float(self.parent.operator.params._ResponseStartMsec[self.channel]) / 1000)+Lookback)*Fs) ) )
        self.Hind.append( int(round( ((float(self.parent.operator.params._ResponseEndMsec[self.channel]) / 1000) + Lookback)*Fs) ) )

        self.Mind = []
        self.Mind.append( int(round( ((float(self.parent.operator.params._ComparisonStartMsec[self.channel]) / 1000)+Lookback)*Fs) ) )
        self.Mind.append( int(round( ((float(self.parent.operator.params._ComparisonEndMsec[self.channel]) / 1000) + Lookback)*Fs) ) )

    def CheckHp2pThreshold(self,x,Hp2p):
        """
        Function to return if Response has been found
        :param x: is the raw trial signal
        :param Hp2p: The H peak to peak value
        :return: If Hp2p >= 2*BGp2p then a response is considered found!
        """

        def ResponseCheck(Amplitude,Threshold):
            if Amplitude >= Threshold: return True
            else: return False

        # Calculate Threshold TODO REMOVE THIS AS WE NOW STORE BG in "self.BGmag"
        BG = [x[self.channel][i] for i in range(self.BGind[0], self.BGind[1])]
        Threshold = 2 * (max(BG) - min(BG))

        return ResponseCheck(Amplitude=Hp2p, Threshold=Threshold)

    def STProcess(self):
        """
        Main process for automated Stimulus Test mode
        Has a subsequence of events if D188 is enabled
        """

        # Set StimulationControl to 0 (we don't want to trigger until we've calculated the next current)
        self.parent.operator.bci2000('Set State StimulationControl 0')

        ProcessCompleted = self.STSubProcess()

        if self.D188ControlEnabled and ProcessCompleted:
            self.D188Control.StoreChannelData(int(self.D188Control.CurrentChannel),self.Hp2p,self.CurrentAmplitude,self.H)
            NextChannel = self.D188Control.ChannelSelection(int(self.D188Control.CurrentChannel),(self.ResponseFound or self.PrevResponseFound),self.Hp2p,self.CurrentAmplitude)

            if NextChannel == -1:
                self.ProcessCompleted = True
                self.parent.Hthreshold = self.D188Control.FinalChannelSelection()
            else:
                #pause the process and see if the user is ready to continue or wants to stop
                self.OptionsDialog = OptionsDialog()
                r = self.OptionsDialog.GetValuePressed()
                if r==1:
                    self.D188Control.SetChannel(Value=NextChannel)
                    self.ResponseCurrent = 0  # When a response is found this is where it is stored for ST
                    self.Delta = 2.0
                    self.PrevResponseFound = False
                    self.ResponseFound = False
                    self.CurrentAmplitude = 3  # float(self.parent.operator.remote.GetParameter('InitialCurrent'))
                    self.ProcessCompleted=False
                    self.H=[]
                    time.sleep(1)
                    # Set StimulationControl == 1
                else:
                    self.ProcessCompleted = True
                    self.parent.Hthreshold = self.D188Control.FinalChannelSelection()


        self.parent.operator.bci2000('Set State StimulationControl 1')
        return self.ProcessCompleted

    def STSubProcess(self):
        """
        Subprocess for automated Stimulus Test mode
        """

        #OK so now a Trial has been completed

        #Function to iterate Delta depending on the response and previous response
        def IterateDelta(ResponseFound,ResponsePrevFound):
            if (ResponsePrevFound): self.Delta /= 2

        #Get H window and Background window
        l = len(self.parent.data[self.mode]) #length of trials so far
        x = self.parent.data[self.mode][l-1]  #get the latest one

        #Correct H
        y = self.CorrectOffset(data=x[self.channel],ind=self.Hind)

        # Calculate H
        self.Hp2p = Hp2p = max(y)-min(y)

        self.PrevResponseFound = self.ResponseFound
        self.ResponseFound =  self.CheckHp2pThreshold(x,Hp2p) #Check against threshold
        if self.ResponseFound:
            self.ResponseCurrent = self.CurrentAmplitude
            self.ResponseAmplitude = Hp2p
            self.H = x

        IterateDelta(self.ResponseFound, self.PrevResponseFound) #Update Delta

        if (self.Delta < self.minDelta):
            self.ProcessCompleted = True

        else:
            #If not then we continue and increment CurrentAmplitdue
            if self.ResponseFound and self.PrevResponseFound:
                self.CurrentAmplitude -= self.Delta
                #Just in case although only happens in simulated data
                if self.CurrentAmplitude <= 0: self.CurrentAmplitude += self.Delta/2
            elif self.ResponseFound: self.CurrentAmplitude +=0
            else: self.CurrentAmplitude += self.Delta

            if self.CurrentAmplitude > self.CurrentLimit:
                self.ProcessCompleted = True

            else:
                #Current increment/decrement decision
                self.parent.stimGUI.SetNewCurrent(value=self.CurrentAmplitude)
                self.parent.stimGUI.SetLabel(self.CurrentAmplitude)
                #self.parent.stimGUI.CurrentAmplitudeState.append(self.CurrentAmplitude)

        return self.ProcessCompleted

    def Threshold(self,Amp, Currents, BG):

        for i, H in enumerate(Amp):
            Found = self.CheckHp2pThreshold(BG[i], H)
            if Found == True:
                return Currents[i-1]

        return -1

    def RCProcess(self):
        """
        Automaically builds a Recruitment Curve
        """

        #If Hmax=True then we are only looking for Hmax (stop after this)
        #Otherwise we are going to Mmax

        def AveragePrevVals(x,i,n): return float(sum(x[n-i:n]))/i

        def NewCurrent():
            self.parent.stimGUI.SetNewCurrent(value=self.CurrentAmplitude)
            self.parent.stimGUI.SetLabel(self.CurrentAmplitude)
            #self.parent.stimGUI.CurrentAmplitudeState.append(self.CurrentAmplitude)

        def DefineNewCurrents(n,Ip):

            #Number of Points we need
            N = min(3 - n,3) #if for some reason we have a -ve GoBack we only need to fill in the N=3

            if N >= 3:
                #Hmax should not == Hthreshold, otherwise we have chosen the wrong starting current
                C = float(self.HmaxCurrent - self.Hthreshold) / (N + 1)
                if self.HmaxCurrent == self.Hthreshold:
                    x = [max([self.Hthreshold - (self.Delta*4),0.25])]
                    x.extend((i*C + self.Hthreshold) for i in range(1,4))
                else:
                    x= [(i*C + self.Hthreshold) for i in range(1,4)]
            elif N == 2:
                x = [(float(Ip[0] - self.Hthreshold)/2 + self.Hthreshold),(float(self.HmaxCurrent - Ip[0])/2 + Ip[0])]
            elif N == 1:
                x = [(float(Ip[0] - Ip[1]) / 2 + Ip[0])]
            else: x = []
            return x

        # Set StimulationControl to 0 (we don't want to trigger until we've calculated the next current)
        self.parent.operator.bci2000('Set State StimulationControl 0')

        #self.Delta = float(self.parent.stimGUI.incrementxt.get())

        if not self.AddingCurrentsState:

            #this will be run incrementally with each new trial to see if we have reached H-max, or M-max or both...
            #Data comes in:

            nHVal = len(self.parent.HwaveMag) #Number of values so far
            Hval = self.parent.HwaveMag

            nMVal = len(self.parent.MwaveMag)  # Number of values so far
            Mval = self.parent.MwaveMag

            nBG = len(self.parent.BGmag)
            BG = self.parent.BGmag

            #We have H and M from self.parent.Hmag and self.parent.Mmag - actually need to pool the results!
            #Average these per self.pooling value

            self.PoolingIndex += 1 #increment this
            if self.PoolingIndex == self.Pooling:
                self.PoolingIndex = 0 #re-inia
                self.HPooledValues.append(AveragePrevVals(Hval,self.Pooling,nHVal))
                self.MPooledValues.append(AveragePrevVals(Mval, self.Pooling, nMVal))
                self.BGPooledValues.append(AveragePrevVals(BG, self.Pooling, nBG))
                C = [float(self.parent.stimGUI.CurrentAmplitudeState[ self.mode ][i])/1000 for i in range(0,nHVal,self.Pooling)]

                nPool = len(self.HPooledValues) #Same for H and M

                if nPool > 2 and self.EndPoint != 'Manual':
                    # Check if H max or M max by comparing to previous values - we need at least 3 currents to know this....
                    if self.HmaxCurrent == 0:
                        self.HmaxReached = self.CheckMax(self.HPooledValues[nPool-1], self.HPooledValues[nPool-2], self.HPooledValues[nPool-3],useC3=True)
                        # Check if we need to do a few more sitmuli to get the slope of the RC.
                        if self.HmaxReached:
                            self.GoBack = (nPool - 3 - 2)  # nVal-3 is the Hmax-1 index, we start 1 Delta below Hthreshold so nPoint is how many points we have between Hmax and Hthreshold
                            l = len(C)
                            if self.GoBack == 1: self.GoBackCurrent = [C[self.GoBack+1]]
                            elif self.GoBack == 2: self.GoBackCurrent = [C[i] for i in range(self.GoBack,self.GoBack+2)]
                            else: self.GoBackCurrent = []
                            self.HmaxCurrent = C[l-3]
                            self.Delta *= 2

                    if self.HmaxReached: self.MmaxReached = self.CheckMax(self.MPooledValues[nPool-1], self.MPooledValues[nPool-2], self.MPooledValues[nPool-3])

                if (self.HmaxReached and self.EndPoint=='Hmax') or (self.MmaxReached and self.EndPoint=='Mmax'): #If we are only to reach Hmax then let's stop this process and check what we are doing next
                    if (self.GoBack < 3):
                        self.Hthreshold = self.Threshold(self.HPooledValues,C,self.BGPooledValues)
                        self.NewCurrents = DefineNewCurrents(self.GoBack,self.GoBackCurrent)
                        self.AddingCurrentsState = True
                        self.CurrentAmplitude = self.NewCurrents[self.AdditionalCurrentIndx]
                        self.AdditionalCurrentIndx += 1
                        self.PoolingIndex = 1
                        NewCurrent()
                        self.parent.operator.bci2000('Set State StimulationControl 1')
                    else:
                        self.ProcessCompleted = True
                else:
                    self.CurrentAmplitude += self.Delta
                    NewCurrent()
                    # Set StimulationControl == 1
                    self.parent.operator.bci2000('Set State StimulationControl 1')
            else:
                self.parent.operator.bci2000('Set State StimulationControl 1')
        else:
            if self.PoolingIndex == self.Pooling:
                self.PoolingIndex = 0
                if self.AdditionalCurrentIndx > len(self.NewCurrents)-1:
                    self.ProcessCompleted = True
                else:
                    self.CurrentAmplitude = self.NewCurrents[self.AdditionalCurrentIndx]
                    self.PoolingIndex += 1
                    self.AdditionalCurrentIndx += 1
                    NewCurrent()
                    self.parent.operator.bci2000('Set State StimulationControl 1')
            else:
                self.PoolingIndex +=1
                self.parent.operator.bci2000('Set State StimulationControl 1')


        return self.ProcessCompleted

    def CTTTProcess(self):
        """
        Automatically control the CT or TT using either Heuristic controller
        """

        #We need to have the Current boundaries we can work with which should be 10-90% between Hthreshold and Hmax although also depends on where MThreshold is
        #Do we need to establish the relationship between BG, M and H for the subject? Possibly over time with CT/TT we can establish this as a means for establishing criteria?


        #Monitor Mmag
        Mmag = numpy.array(self.parent.MwaveMag)
        L = Mmag.size
        #Mmedian = numpy.median(Mmag)

        output = self.h.Update(NewValue=Mmag[L-1])
        #if output != 0: NewCurrent = self.CurrentTarget + (self.h.Setpoint*(output/100)/self.h.Gradient)
        if output != 0: 
            NewCurrent = round(output,1) #self.CurrentAmplitude
            print('Updated Stim Current - ',NewCurrent)
        else: NewCurrent = self.CurrentAmplitude
        #TODO - USE Current Target or CurrentAmplitude? If Latter we may need to re-calculate/estimate the Ctarget
        #NewCurrent = self.CurrentAmplitude + ( (output*self.CurrentAmplitude)/100 )

        if NewCurrent > self.CurrentRange[1]: NewCurrent = self.CurrentRange[1]
        elif NewCurrent < self.CurrentRange[0]: NewCurrent = self.CurrentRange[0]
        self.CurrentAmplitude = int(NewCurrent)

		
        def SetNewCurrent():
            self.parent.stimGUI.SetNewCurrent(value=NewCurrent)
            self.parent.stimGUI.SetLabel(NewCurrent)
        
        if self.CurrentAmplitude < float(self.CurrentLimit)*1000: SetNewCurrent()

        return

    def CheckMax(self,cVal,pVal,ppVal,useC3=False):
        """
        Used in Recruitment Curve (RCProcess) to check if we have an H or M max
        :param cVal: Current H or M value [x]
        :param pVal: Previous H or M value [x-1]
        :param ppVal: Previous Prevous H or M value [x-2]
        :param useC3: Optional 4rd criteria to avoid detection of M/H saturation when no threshold found ye
        :return:
        """

        #Function to check if we have reached H or M Max
        #ppVal represents Hmax if true - i.e. we check the next two values to see the result
        #cVal = x[i], pVal = x[i-1], ppVal = x[i-2]

        Criteria1a = (pVal < 1.15*ppVal) and (pVal > 0.85*ppVal)
        Criteria1b = (cVal < 1.15*pVal) and (cVal > 0.85*pVal)
        Criteria2a = pVal < ppVal*0.9
        Criteria2b = cVal < ppVal*0.9

        l = len(self.parent.data[self.mode])  # length of trials so far
        x = self.parent.data[self.mode][l - 1]  # get the latest one

        if useC3: Criteria3 = self.CheckHp2pThreshold(x, cVal) #3rd criteria checking if curent p2p is above threshold otherwise Criteria1a and b will be true subthreshold
        else: Criteria3 = True

        if ((Criteria1a and Criteria1b) or (Criteria2a and Criteria2b)) and (Criteria3): return True
        else: return False

    def CorrectOffset(self,data, ind):
        """
        If there is an offset on the H due to the tail of a stimulation artefact, this corrects
        :param data: Raw data of a single trial
        :param ind: indices to create and subtract a linear model offset estimate from
        :return:
        """
        N = (ind[1] - ind[0])
        y = self.LinearRegression(y1=data[ind[0]], y2=data[ind[1]], N=N)
        z = [0] * N
        for i, yi in enumerate(y): z[i] = data[ind[0] + i] - yi
        return z

    def LinearRegression(self,y1,y2,N):
        """
        Called by CorrectOffset - Simple calculator of Gradient and Y-intercept to contstruct a crude linear model of data
        Return y, where y[1]=y1, and y[N]=y2
        The H-reflex is less affected by any stimulus artefact and at this distance from the artefact can be approximated by a linear function
        """
        M = (y2-y1)/N
        C = y1 - M
        y = [0]*N
        for i in range(0,N): y[i] = M*i + C
        return y

    def ProcessCompletion(self,mode=None):
        """
        If STProcess, RCProcess or CTTTProcess return that thier processes are completed then this sets the appropriate variables.

        For ST it calculates the best location (if not using the D188 - this is a special case handled by the D188Control Class)
        For RC it calculates the best RC stimulation location and populates RCStorage in stimGUI (from CurrentControl class)

        """
        self.parent.BackgroundSet = 0
        if self.mode in ['st']:
            #D188 parameters are handled in
            if not hasattr(self.parent, 'D188Control'):
                if self.parent.ControlObject.ResponseCurrent == 0:
                    indx = len(self.parent.stimGUI.CurrentAmplitudeState[ self.mode ]) - 1  # no response found
                    Dialog(self.parent, modal=False, message="No threshold found", buttons=['OK'])
                else:
                    indx = self.parent.stimGUI.CurrentAmplitudeState[ self.mode ].index(
                        self.parent.ControlObject.ResponseCurrent * 1000)  # find the index of the trial corresponding to the current currently set
                    Dialog(self.parent, modal=False, message="H-reflex threshold found at: " + str(self.parent.ControlObject.ResponseCurrent) + "mA",buttons=['OK'])

                self.parent.stimGUI.STDataStorage.append(self.parent.data[self.mode][indx])
                self.parent.stimGUI.addLocation(value1=self.parent.ControlObject.ResponseCurrent,value2=self.parent.ControlObject.ResponseAmplitude)
        if self.mode in ['rc']:  # Recruitment Curve and the Process has been completed
            Dialog(self.parent, modal=False, message="Process Completed!", buttons=['OK'])
            #if self.parent.multigrid: self.parent.stimGUI.RCStorageClear()
            #self.parent.stimGUI.RCStorage['data'].append(self.parent.data[self.mode])
            #self.parent.stimGUI.RCStorage['currents'].append(self.parent.stimGUI.CurrentAmplitudeState)
            #self.parent.stimGUI.RCStorage['stimpool'].append(self.parent.ControlObject.Pooling)
            #self.parent.stimGUI.RCStorage['run'].append(self.parent.GetDescription(self.mode))
            #self.parent.stimGUI.RCStorage['log'].append(0)
            #if self.parent.states[self.mode].TrialsCompleted > 10:
            #    (Use, Current, Grad, Min, Max, Mtarget) = self.parent.RCanalysis.DetermineCurrent(self.parent.HwaveMag, self.parent.MwaveMag,
            #                                                                               self.parent.BGmag,
            #                                                                               self.parent.stimGUI.CurrentAmplitudeState,
            #                                                                               self.parent.ControlObject.Pooling,
            #                                                                               self.parent.data[self.mode])
            #    Mmax = max(self.parent.MwaveMag); Hmax = max(self.parent.HwaveMag)
            #else:
            #    Use = -1; Current = 0;  Grad = 0; Min = 0; Max = 0; Mtarget = 0; Mmax = 0; Hmax = 0

            #self.parent.stimGUI.RCStorage['optcurrent'].append(Current)
            #self.parent.stimGUI.RCStorage['use'].append(Use)
            #self.parent.stimGUI.RCStorage['grad'].append(Grad)
            #self.parent.stimGUI.RCStorage['Min'].append(Min)
            #self.parent.stimGUI.RCStorage['Max'].append(Max)
            #self.parent.stimGUI.RCStorage['Mtarget'].append(Mtarget)
            #self.parent.stimGUI.RCStorage['Mmax'].append(Mmax)
            #self.parent.stimGUI.RCStorage['Hmax'].append(Hmax)


class PreRCstart(tkinter.Toplevel):
    """
    A class that control pre Recruitment Curve to make sure that the Background has been set and or the Hthreshold
    """

    def __init__(self,parent,StimLocations=None,SessionType='Screening',BGset=-1):
        """
        Initialization of the window and features
        :param parent: Main GUI
        :param StimLocations: If needed
        :param SessionType:
        :param BGset:
        """

        tkinter.Toplevel.__init__(self,parent,bg='white')
        frame = tkinter.Frame(self)
        frame['bg'] = 'white'
        self.StimLocations = StimLocations
        self.parent = parent


        # Flags for when we can move on
        self.HthresholdSet = False

        #background is set as -1: RC never run before, 0: There have been previous RC runs so we are unsure if a new Background is needed, or 1: All set and good.
        self.BackgroundSet = BGset

        self.ScreeningType = SessionType

        self.Body(frame,StimLocations=StimLocations)

        self.wm_attributes("-topmost", 1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.transient(parent)

        frame.pack(side='top', fill='both', expand=True, padx=5, pady=5)

        self.geometry("%dx%d+%+s" % (460 , 125, self.parent.geometry().split('+',1)[1]))

        self.wait_window()

    def Body(self,frame,StimLocations):
        """
        Construct the Main Body
        :param frame: A frame is generated using Tkinter TopLevel
        :param StimLocations: We need the user to select the stimulation location they or the system has chosen
        """

        bg = frame['bg']

        fontSMALL = ('Helvetica', 10)
        fontMED = ('Helvetica', 12)
        fontLARGE = ('Helvetica', 14)

        self.BGlabel = w = tkinter.Label(frame,text='Set Background:',font=fontLARGE,bg=bg)

        w.grid(row=0,column=0,columnspan=2,padx=1,pady=3)

        self.BGauto_button = w = tkinter.Button(frame, text='Automatic', font=fontMED, command=lambda: self.AutoBG())
        w.grid(row=0, column=2,padx=3)
        self.BGmanual_button = w = tkinter.Button(frame, text='Manual', font=fontMED, command=lambda: self.ManualBG())
        w.grid(row=0, column=3,padx=3)

        self.background_indicator_canvas = w = tkinter.Canvas(frame, width=20, height=20, borderwidth=0, highlightthickness=0,
                                                       bg=bg)
        w.grid(row=0, column=4, padx=2)

        #Setting the indicators that the
        if self.BackgroundSet==1: self.background_indicator = w.create_oval(20, 20, 0, 0 , fill="green", outline="black", width=1)
        elif self.BackgroundSet==-1: self.background_indicator = w.create_oval(20, 20, 0, 0 , fill="red", outline="black", width=1)
        else: self.background_indicator = w.create_oval(20, 20, 0, 0 , fill="orange", outline="black", width=1)

        self.Hlabel = w = tkinter.Label(frame, text='Set H-Threshold:', font=fontLARGE,bg=bg)
        w.grid(row=1, column=0,columnspan=2, padx=1, pady=3)

        self.menuVar = tkinter.StringVar()
        MenuOptions = []
        CurrentThreshold = []
        Amplitudes = []
        for keys,values in StimLocations.iteritems():
            MenuOptions.append(keys)
            CurrentThreshold.append(values[0])
            Amplitudes.append(values[1])

        self.StimLocationsOptionMenu = w = tkinter.OptionMenu(frame, self.menuVar,'', *MenuOptions,command=self.ChangeLabel)

        w['menu'].config(bg=bg); w['menu'].config(font=fontSMALL)
        w.config(bg=bg); w.config(width=6,borderwidth=0)
        w.grid(row=1,column=2,padx=3,pady=3)

        self.Hthreshold = tkinter.StringVar()
        self.StimLocationLabel = w = tkinter.Entry(frame,textvariable=self.Hthreshold,font=fontMED,background=bg,width=8)
        w.grid(row=1, column=3, padx=3, pady=1)

        self.hthreshold_indicator_canvas = w = tkinter.Canvas(frame, width=20, height=20, borderwidth=0, highlightthickness=0, bg=bg)
        w.grid(row=1, column=4, padx=2)

        if len(StimLocations) > 0:

            #When run for the first time after and ST, we do not have an idea of the best and/or chosen location
            #So do this, next time the else will be processed.
            if (self.parent.StimLocation == None) or (self.parent.StimLocation == []):
                #StimCurrents = StimLocations.values()

                #Now StimLocations values contains both the threshold and amplitude
                #Only show the Thresholds that are non zero
                indx = [i for i, e in enumerate(CurrentThreshold) if e != 0]

                #Find the minimum Threshold
                minThreshold = min([CurrentThreshold[i] for i in indx])

                #Fidn the indices of thresholds that are == to the minimum, and extract the amplitude at these
                indx = []; Hamp_temp = []
                for i, e in enumerate(CurrentThreshold):
                    if e == minThreshold:
                        indx.append(i)
                        Hamp_temp.append(Amplitudes[i])

                #Which one has the minimal amplitude?
                minAmp = max(Hamp_temp)
                #Therefore the one we want is:
                idx_minThreshold = indx[Hamp_temp.index(minAmp)]

                self.parent.StimLocation = MenuOptions[idx_minThreshold]
            else:
                idx_minThreshold = MenuOptions.index(self.parent.StimLocation)
                minThreshold = CurrentThreshold[idx_minThreshold]

            self.menuVar.set(MenuOptions[idx_minThreshold])
            self.Hthreshold.set(str(minThreshold) + 'mA')
            self.hthreshold_indicator = w.create_oval(20, 20, 0, 0, fill="green", outline="black", width=1)
        else:
            self.hthreshold_indicator = w.create_oval(20, 20, 0, 0, fill="red", outline="black", width=1)
        self.Hthreshold.trace(mode="w", callback=self.OnThresholdChange())
        self.OnThresholdChange()

        self.Cancel_button = w = tkinter.Button(frame, text='Cancel', font=fontLARGE, command=lambda: self.close())
        w.grid(row=3,column=3,padx=1,pady=5)
        self.Continue_button = w = tkinter.Button(frame, text='Continue>>', font=fontLARGE, command=lambda: self.Continue())
        w.grid(row=3, column=4, padx=1, pady=5)

    def close(self):
        """
        Standard close of the window
        Sets self.Succesful to False if closed so that automation does not continue
        """
        self.Successful = False
        self.destroy()

    def Continue(self):
        """
        Called by the Continue button
        Will return a true via self.Successful if the Background and Hthreshold have been set
        """
        self.OnThresholdChange()
        if self.HthresholdSet and ((self.BackgroundSet==0) or (self.BackgroundSet==1)):
            self.Successful = True
        else:
            self.Successful = False

        self.destroy()

    def OnThresholdChange(self,value=0,extra=0,extra2=0):
        """
        If the user manually changes the threshold we link (using trace) to this function to test that it is a valid number

        Input variables are a consequence of trace and are unused
        """

        s = self.Hthreshold.get()
        indmA = s.find('mA')
        if indmA == -1: indmA = len(s)+1

        try:
            float(s[0:indmA])
            self.HthresholdSet = True
            self.hthreshold_indicator_canvas.itemconfig(self.hthreshold_indicator,fill="green")
            self.parent.Hthreshold = float(s[0:indmA])
        except:
            self.hthreshold_indicator_canvas.itemconfig(self.hthreshold_indicator,fill="red")

    def ChangeLabel(self,value):
        """
        If the dropdown box of stimulation locations is changed, this will updae the Hthreshold label
        """

        try:
            self.Hthreshold.set(str(self.StimLocations[self.menuVar.get()][0]) + 'mA')
            self.parent.StimLocation = self.menuVar.get()
        except:
            return None

    def AutoBG(self):
        """
        If Automatically setting the Background range this controls this, by switching to VC

        Setting self.parent.BackgroundCheck to True will cause BackgroundCheck class to be initiated in VC mode when started
        """
        #Run without any automation
        self.parent.operator.bci2000('Set State StimulationControl 0')
        self.parent.stimGUI.Automate.set(0)
        # Set current to 0mA so no stimulation just in case
        self.parent.stimGUI.SetNewCurrent(value=0)
        self.parent.stimGUI.SetLabel(0.0)
        #Let the system know we are now just recording and only recording BG
        # Setting these starts a chain of events in VC mode to run class Background check
        self.parent.mode = 'vc'; self.parent.BackgroundCheck = True
        self.parent.SelectTab('vc')
        self.close()

    def ManualBG(self):
        """
        If user chooses to manually configure background turn off automation and close the window
        """
        self.parent.stimGUI.Automate.set(0)
        self.parent.BackgroundSet = True
        self.close()

        return

class PreCTstart(tkinter.Toplevel):
    """
    Before a CT/TT, if automted, we need to ascertain the parameters to use. This displays a window that is extracted from RCStorage that will enable automation
    """
    def __init__(self, parent,RCindex):
        """
        A window initiated as a Tkinter TopLevel
        """
        tkinter.Toplevel.__init__(self, parent, bg='white')
        frame = tkinter.Frame(self)
        #frame['bg'] = 'white'

        self.parent = parent

        self.Body(frame)
        self.RCindex = RCindex

        self.wm_attributes("-topmost", 1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.transient(parent)

        frame.pack(side='top', fill='both', expand=True, padx=5, pady=5)

        self.geometry("%dx%d+%+s" % (580, 100, self.parent.geometry().split('+', 1)[1]))

        self.wait_window()

    def Body(self, frame):
        """
        Main body of the window
        """

        bg = 'white'

        fontSMALL = ('Helvetica', 11)
        fontLARGE = ('Helvetica', 12)

        #Editable list of the Run number, StimCurrent, Min/Max...
        D = self.RCindex
        (Min, Max) = (self.parent.stimGUI.RCStorage['Min'], self.parent.stimGUI.RCStorage['Max'])
        optcurrent = self.parent.stimGUI.RCStorage['optcurrent']
        run = self.parent.stimGUI.RCStorage['run']
        Mtarget = self.parent.stimGUI.RCStorage['Mtarget']
        gradient = self.parent.stimGUI.RCStorage['grad']

        #Run menu
        w = tkinter.Label(frame,text='Run',font=fontLARGE)
        w.grid(row=0, column=0, columnspan=1, padx=5)
        self.menuVar = tkinter.StringVar()
        self.RunMenu = w = tkinter.OptionMenu(frame, self.menuVar, '', *run, command=self.ChangeLabel)

        w['font'] = fontSMALL; w['menu'].config(bg=bg); w['menu'].config(font=fontSMALL)
        w.config(bg=bg); w.config(width=6, borderwidth=0)
        w.grid(row=1, column=0, columnspan=1, padx=5)
        self.menuVar.set(run[D])

        #Stimulation current
        w = tkinter.Label(frame, text='Current (mA)',font=fontLARGE)
        w.grid(row=0, column=1, columnspan=1, padx=5)
        self.StimLabelVar = tkinter.StringVar()
        self.StimLabel = w = tkinter.Entry(frame,textvariable=self.StimLabelVar,bg=bg,width=5,font=fontSMALL)
        self.StimLabelVar.set('{:.2f}'.format(float(optcurrent[D])/1000))
        w.config(width=6, borderwidth=0)
        w.grid(row=1, column=1, columnspan=1, padx=5)

        #Target M
        w = tkinter.Label(frame, text='Target M (mV)',font=fontLARGE)
        w.grid(row=0, column=2, columnspan=1, padx=5)
        self.MtargetVar = tkinter.StringVar()
        self.MtargetEntry = w = tkinter.Entry(frame, textvariable=self.MtargetVar,bg=bg,width=5,font=fontSMALL)
        self.MtargetVar.set('{:.2f}'.format(float(Mtarget[D])*1000))
        w.config(width=6, borderwidth=0)
        w.grid(row=1, column=2, columnspan=1, padx=5)

        #Min/Max range
        w = tkinter.Label(frame, text='Min (mA)',font=fontLARGE)
        w.grid(row=0, column=3, columnspan=1, padx=5)
        self.MinVar = tkinter.StringVar()
        self.MinEntry = w = tkinter.Entry(frame, textvariable=self.MinVar,bg=bg,width=5,font=fontSMALL)
        self.MinVar.set('{:.2f}'.format(float(Min[D])/1000))
        w.config(width=6, borderwidth=0)
        w.grid(row=1, column=3, columnspan=1, padx=5)

        w = tkinter.Label(frame, text='Max (mA)',font=fontLARGE)
        w.grid(row=0, column=4, columnspan=1, padx=5)
        self.MaxVar = tkinter.StringVar()
        self.MaxEntry = w = tkinter.Entry(frame, textvariable=self.MaxVar,bg=bg,width=5,font=fontSMALL)
        self.MaxVar.set('{:.2f}'.format(float(Max[D])/1000))
        w.config(width=6, borderwidth=0)
        w.grid(row=1, column=4, columnspan=1, padx=5)

        #Gradient
        w = tkinter.Label(frame, text='Gradient',font=fontLARGE)
        w.grid(row=0, column=5, columnspan=1, padx=5)
        self.GradientVar = tkinter.StringVar()
        self.GradientEntry = w = tkinter.Entry(frame, textvariable=self.GradientVar,bg=bg,width=5,font=fontSMALL)
        self.GradientVar.set(gradient[D])
        w.config(width=6, borderwidth=0)
        w.grid(row=1, column=5, columnspan=1, padx=5)

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        self.Cancel_button = w = tkinter.Button(frame, text='Cancel', font=fontLARGE, command=lambda: self.close())
        w.grid(row=2, column=4, padx=1, pady=5)
        self.Continue_button = w = tkinter.Button(frame, text='Continue>>', font=fontLARGE,command=lambda: self.Continue())
        w.grid(row=2, column=5, padx=1, pady=5)


    def ChangeLabel(self,value=0,extra=0,extra2=0):
        """
        If we change the choice of RC in which to derive our automatic control of CT/TT then this will populate the fields in the window
        """

        run = self.parent.stimGUI.RCStorage['run']
        choice = self.menuVar.get()

        if choice == '': return

        indx = run.index(choice)

        (Min, Max) = (self.parent.stimGUI.RCStorage['Min'], self.parent.stimGUI.RCStorage['Max'])
        optcurrent = self.parent.stimGUI.RCStorage['optcurrent']

        Mtarget = self.parent.stimGUI.RCStorage['Mtarget']
        gradient = self.parent.stimGUI.RCStorage['grad']

        self.MtargetVar.set(Mtarget[indx] * 1000)
        self.StimLabelVar.set(float(optcurrent[indx]) / 1000)
        self.MaxVar.set(float(Max[indx]) / 1000)
        self.MinVar.set(float(Min[indx]) / 1000)
        self.GradientVar.set(gradient[indx])

        return

    def close(self):
        """
        Standard Close function
        """
        self.Successful = False
        self.destroy()

    def Continue(self):
        """
        When continue is pressed we re-store the values in the fields, in case any have been changed
        """


        run = self.parent.stimGUI.RCStorage['run']
        choice = self.menuVar.get()

        if choice == '': return

        indx = run.index(choice)

        self.parent.stimGUI.RCStorage['Min'][indx] = float(self.MinVar.get())*1000
        self.parent.stimGUI.RCStorage['Max'][indx]= float(self.MaxVar.get())*1000
        self.parent.stimGUI.RCStorage['optcurrent'][indx]= float(self.StimLabelVar.get())*1000
        self.parent.stimGUI.RCStorage['Mtarget'][indx] = float(self.MtargetVar.get())/1000
        self.parent.stimGUI.RCStorage['grad'][indx]= float(self.GradientVar.get())

        #if self.parent.operator.params._AutoWindows == 'yes':
        #    self.parent.operator.Set(_ComparisonStartMsec=[self.parent.stimGUI.RCStorage['Mwin'][indx][0], self.parent.stimGUI.RCStorage['Mwin'][indx][0]],_ComparisonEndMsec=[self.parent.stimGUI.RCStorage['Mwin'][indx][1], self.parent.stimGUI.RCStorage['Mwin'][indx][1]])
        #    self.parent.operator.Set(_ResponseStartMsec=[self.parent.stimGUI.RCStorage['Hwin'][indx][0],self.parent.stimGUI.RCStorage['Hwin'][indx][0]],_ResponseEndMsec=[self.parent.stimGUI.RCStorage['Hwin'][indx][1],self.parent.stimGUI.RCStorage['Hwin'][indx][1]])

        #If M-wave Window, update overlay.
        if hasattr(self.parent,'mwaveGUI'):
            self.parent.mwaveGUI.widgets.entry_meanVar.variable.set(str('{:.3f}'.format(float(self.MtargetVar.get()))))
            self.parent.mwaveGUI.RegionUpdate()

        self.Successful = True
        self.destroy()

class BackgroundCheck(object):
    """
    Class for calculating the background EMG limits of the target muscle (e.g. Soleus, FCR...)
    """

    def __init__(self,parent):
        """
        User will be asked to relax for 5seconds when ready and the Background will be captured
        """

        # Ask to relax and run 5 seconds
        self.Proceed = False
        self.parent = parent

        Fs = self.parent.fs
        SBS = self.parent.sbs
        BlockTime = SBS / Fs #40ms
        self.CheckTime = 1000.0 #ms
        self.iter = 1
        self.NoBlocks = int(((self.CheckTime/1000) / BlockTime) + 0.5)


        self.BGmax = self.parent.operator.params._BackgroundMax[0]
        self.BGmin = self.parent.operator.params._BackgroundMin[0]
        self.BGmaxArray = numpy.array([])
        self.BGminArray = numpy.array([])

        if tkMessageBox.askokcancel("","When relaxed please press OK and the background will be determined!"):
            self.Proceed = True
        return

    def CheckCurrentBG(self):
        """
        Function will check how much data we have in VC mode and Determine when background has settled to a norm

        This does this by setting initial values and then adjusting the background to meet a criteria for the number of crossing and
        percentage of the BG that crosses the threshold - the latter gives us an idea of the area above threshold, rather than the former
        that focuses on intermittent bursts of threshold crossings

        Will return ProcessCompleted if enough data has been gathered and that data is settled such that the criteria are met
        """

        data = numpy.trim_zeros(numpy.asarray(self.parent.data['vc']))
        l = len(data)
        ProcessCompleted = False

        if l >= self.NoBlocks*self.iter:

            data_temp = data[l-self.NoBlocks:l]

            mData = numpy.median(data_temp)
            BGmax = 1.7*mData
            BGmin = 0.55*mData

            m = 0; i = 0
            while (m != 1):
                [CrossCount, PercCrossCount] = self.CheckCrossings(data_temp,BGmax,Above=True)
                mp=m
                m = self.CheckCriteria(CrossCount, PercCrossCount)

                if (i > 10) or (i>0 and mp != m):
                    m = 1
                    BGmax *= m
                else:
                    BGmax = BGmax*m
                    i += 1

            m = 0; i = 0
            while (m != 1):
                [CrossCount, PercCrossCount] = self.CheckCrossings(data_temp,BGmin,Above=False)
                mp = m
                m = self.CheckCriteria(CrossCount, PercCrossCount)
                if (i > 10) or (i>0 and mp != m):
                    m = 1
                    BGmin = BGmin*(mp)
                else:
                    BGmin = BGmin*(2-m)
                    i += 1

            self.BGmaxArray = numpy.append(self.BGmaxArray,BGmax*1.1)
            self.BGminArray = numpy.append(self.BGminArray,BGmin*0.9)

            self.iter += 1

        if self.iter > 5:

            dMax = numpy.diff(self.BGmaxArray)
            dMin = numpy.diff(self.BGminArray)

            ProcessCompleted = any(numpy.diff(self.BGmaxArray, 2) < 1e-3) and any(numpy.diff(self.BGminArray,2) < 1e-3)

        if ProcessCompleted:
            indMax = numpy.where((numpy.diff(self.BGmaxArray, 2) < 1e-3) == True); indMax = indMax[0]
            indMin = numpy.where((numpy.diff(self.BGminArray, 2) < 1e-3) == True); indMin = indMin[0]

            for i in indMax: indMax = numpy.append(indMax,[i, i + 1, i + 2])
            for i in indMin: indMin = numpy.append(indMin,[i, i + 1, i + 2])
            indMax = numpy.unique(indMax); indMin = numpy.unique(indMin)

            BGmax = numpy.median(self.BGmaxArray[indMax]); BGmin = numpy.median(self.BGminArray[indMin])
            if (BGmax - BGmin) < 0.01:
                BGmax += (0.01-(BGmax-BGmin))/2
                BGmin -= (0.01-(BGmax-BGmin))/2

            BGmin = max(BGmin,0) #Just in case we pull it negative

            self.parent.operator.params._BackgroundMax[0] = int(BGmax*1000)
            self.parent.operator.params._BackgroundMin[0] = int(BGmin*1000)


        return ProcessCompleted

    def CheckCrossings(self,data,Threshold,Above=True):
        """
        Called by CheckCurrentBG to measure the number of and percentage of data that crosses the threshold

        """

        # check how many crossings there are and percentage above max/min
        # If there is none then we can lower BGmax or raise BGmin by 10%
        # If at least 1% of the signal is avove the BGmax and the Number of Crossing is >2 then increase BGmax (equiv for BGmin) or if Crossings is > 10 or %crossed > 3
        if Above: temp = (data > Threshold)
        else: temp = (data < Threshold)
        l = len(data)
        temp_p = numpy.append(False, temp[0:len(temp) - 1])
        temp_f = numpy.append(temp[1:len(temp)], False)

        PercCrossCount = 100*float(numpy.sum(temp)) / l

        idx1 = numpy.where(numpy.logical_and((temp == True), (temp_p == False)))
        idx1 = idx1[0]
        idx2 = numpy.where(numpy.logical_and((temp_f == False), (temp == True)))
        idx2 = idx2[0] + 1

        tempC = []
        for i, idxi in enumerate(idx1):
            tempC.append(numpy.sum(temp[idxi:idx2[i]]))

        if len(tempC)>0: CrossCount = numpy.max(tempC)
        else: CrossCount = 0

        return CrossCount, PercCrossCount
    def CheckCriteria(self,CrossCount,PercCrossCount):
        """
        Checks against the criteria

        Note: May seem arbitrary but was determined from plowing through old data
        """

        if (CrossCount > 10) or (PercCrossCount > 3) or ((CrossCount>2) and (PercCrossCount>1)):
            return 1.1
        elif (PercCrossCount==0) and (CrossCount == 0):
            return 0.9
        else: return 1

class RCAnalysis(object):
    """
    Class RCAnalysis is involved with the analsis of RC data for determining the optimal stimulation current
    """

    def __init__(self, parent):

        self.channel=0
        self.parent=parent

    def CheckHp2pThreshold(self,BGp2p,Hp2p):

        """
        Function to return if Response has been found (analogous to class CurrentControl)
        """

        def ResponseCheck(Amplitude,Threshold):
            if Amplitude >= Threshold: return True
            else: return False

        Threshold = 2 * BGp2p

        return ResponseCheck(Amplitude=Hp2p, Threshold=Threshold)

    def FindMax(self,Amplitudes,BGAmplitudes,Currents):
        """
        Function finds Hmax or Mmax in an array of currents and amplitudes
        """

        # set up the current value etc.
        for i in range(2, numpy.size(Amplitudes)):
            cVal = Amplitudes[i];  pVal = Amplitudes[i - 1];  ppVal = Amplitudes[i - 2]

            # check criteria
            Criteria1a = (pVal < 1.1 * ppVal) and (pVal > 0.9 * ppVal)
            Criteria1b = (cVal < 1.1 * pVal) and (cVal > 0.9 * pVal)
            Criteria2a = pVal < ppVal * 0.9
            Criteria2b = cVal < ppVal * 0.9

            # 3rd criteria checking if curent p2p is above threshold otherwise Criteria1a and b will be true subthreshold

            Criteria3 = self.CheckHp2pThreshold(BGAmplitudes[i-2],ppVal)

            if ((Criteria1a and Criteria1b) or (Criteria2a and Criteria2b)) and (Criteria3):
                return Currents[i-2]

        return -1

    def FindHmax(self,Amplitudes,BGAmplitudes,Currents):
        """
        Function finds Hmax only in an array of currents and amplitudes
        """

        UpSlope = 0; DownSlope = -1

        for i in range(2, numpy.size(Amplitudes)):
            cVal = Amplitudes[i]; pVal = Amplitudes[i - 1]; ppVal = Amplitudes[i - 2]

            # check criteria for upslope saturation
            Criteria1a = (pVal < 1.1 * ppVal) and (pVal > 0.9 * ppVal)
            Criteria1b = (cVal < 1.1 * pVal) and (cVal > 0.9 * pVal)

            # check criteria for downslope saturation
            Criteria2a = pVal < ppVal * 0.9
            Criteria2b = cVal < ppVal * 0.9

            # 3rd criteria checking if curent p2p is above threshold otherwise Criteria1a and b will be true subthreshold

            Criteria3 = self.CheckHp2pThreshold(BGAmplitudes[i - 2], ppVal)

            if (Criteria1a and Criteria1b) and (Criteria3):
                UpSlope = i-2
            if (Criteria2a and Criteria2b) and (Criteria3):
                DownSlope = i-2
                break

        if (DownSlope == -1):
            return -1
        else:
            m = -1
            indx = -1
            for i in range(UpSlope,DownSlope+1):
                if Amplitudes[i] > m:
                    m = Amplitudes[i]
                    indx = i

            if indx != -1: return Currents[indx]
            else: return -1



    def Threshold(self,Amp, Currents, BG):
        """
        Simple function to return if signal response is above threshold
        """

        for i, H in enumerate(Amp):
            Found = self.CheckHp2pThreshold(BG[i], H)
            if Found == True:
                return Currents[i]

        return -1

    def ResponseMagnitudes(self,data, interval, fs, lookback, p2p=False,SingleTrial=False):
        """
        A rehash of the CoreFunction Response Magnitudes tailored to different types of data
        :param data: Raw data trial or trails
        :param interval: response interval (e.g. H)
        :param fs: Sampling Frequency
        :param lookback: How much signal (ms) is captured pre-stimulus
        :param p2p: Analyzing peak-to-peak or rms?
        :param SingleTrial: If only one trial of data (Could be tested with duck typing)
        :return: amplitude(s)
        """

        interval = min(interval), max(interval)
        start, length = interval[0], interval[1] - interval[0]
        start = round((start + lookback) * fs)
        length = round(length * fs)
        r = []
        if SingleTrial:
            y = data
            y = [yi for i, yi in enumerate(y) if start <= i < start + length]
            if p2p:
                r.append(max(y) - min(y))
            else:
                r.append(sum(abs(yi) for yi in y) / float(len(y)))
        else:
            for trial in data:
                y=trial
                y = [yi for i, yi in enumerate(y) if start <= i < start + length]
                if p2p:
                    r.append(max(y) - min(y))
                else:
                    r.append(sum(abs(yi) for yi in y) / float(len(y)))
        return r

    def DetermineCurrent(self,HAmplitudes,MAmplitudes,BGAmplitudes,Currents,Pooling,RawData):
        """
        Find the lowest current that has a small detectable M, High Mmax and Hmax
        # Simple choice is the highest Mmax and Hmax location, then find the stim
        # More complex is to consider both and to find a detectable M even if not the largest H or M max
        # Also to add the slope of the M-wave around the threshold chosen
        :param HAmplitudes: Channel/Signal/Trial H-reflex amplitude
        :param MAmplitudes: Channel/Signal/Trial M-wave amplitude
        :param BGAmplitudes: Channel/Signal/Trial Background amplitude
        :param Currents: Currents being used for this run
        :param Pooling: Number of stim per current
        :param RawData: Raw EMG trial data, as we need it to compute the RMS values
        :return:
        """

        #Function for sorting the Amp, Currents
        def Pool(Amps, Currents, Pooling):
            """
            Pool and correct currents here
            """

            (r, c) = Amps.shape
            N = int(Pooling * round((c / Pooling) - 0.5))  # In case we have an extra current

            A = numpy.empty((r, N / Pooling))

            for n in range(0, r):
                Amp = numpy.asarray(Amps[n, 0:N])
                AmpsPooled = numpy.asarray([])

                for k,i in enumerate(range(0, N, Pooling)):
                    AmpsPooled = numpy.append(AmpsPooled, numpy.mean(Amp[i:i + Pooling]))

                A[n, :] = AmpsPooled

                # Sort the currents
            #if len(Currents) == len(Amp):
            C = numpy.asarray(Currents[0:N:Pooling])
            #else:
            #    C = Currents

            return (A, C)

        def FindTangentSlope(dC, AMP1, AMP2):
            """
            Finds the gradient of two values e.g. dHamp/dCurrent
            """
            return (AMP2 - AMP1) / dC

        def CalculateMtarget(Mamps,Camps,Ctarget):
            """
            Estimate the target M-wave amplitude (RMS) to be used in CT/TT
            """

            #find closest Current
            indxC = numpy.where(numpy.abs(C - Ctarget) == numpy.abs(C - Ctarget).min())[0]

            if isinstance(indxC,numpy.ndarray): indxC = indxC[0]

            if indxC == 0:
                Mtemp = Mamps[indxC:indxC + 3]
                Ctemp = Camps[indxC:indxC + 3]
                G = numpy.array(0)
                G = numpy.append(G,numpy.diff(Mtemp) / numpy.diff(Ctemp))
            else:
                Mtemp = Mamps[indxC-1:indxC + 3]
                Ctemp = Camps[indxC-1:indxC + 3]
                G = numpy.diff(Mtemp) / numpy.diff(Ctemp)

            #current estimate is an average of the linear interpolant for each gradient
            N1 = (Mtemp[1] + (G[0] * (Ctarget - Ctemp[1])))
            N2 = (Mtemp[2] - (G[1] * (Ctemp[2] - Ctarget)))
            output = (N1+N2)/2

            if ((Ctarget-Ctemp[1]) == 0) or ((Ctemp[2]-Ctarget) == 0):
                gradient = 0.001
            else:
                gradient = (((output-Mtemp[1])/(Ctarget-Ctemp[1])) + ((Mtemp[2]-output)/(Ctemp[2]-Ctarget)))/2

            return (gradient,output)

        def Reorder(C,A):
            """
            Reorder the currents and amplitudes as the currents may not be monotonic
            :param C: Currents
            :param A: Amplitude signals
            :return: Sorted signals
            """

            (r,c) = A.shape
            Asorted = numpy.empty((r,c))
            Csorted = []

            if C != []:

                Csorted = sorted(C)
                cindx = sorted(range(len(C)), key=lambda k: C[k])
                # Need to refine this for pooled data
                for n in range(0,r):
                    Asorted[n,:] = [A[n,k] for k in cindx]

            return Asorted, Csorted

        #Refine H,M windows and update

        #Calculate the Mean Rectified Amplitude of M
        Data = [Di[self.channel] for Di in RawData]
        ind1 = float(self.parent.operator.params._ComparisonStartMsec[self.channel]) / 1000
        ind2 = float(self.parent.operator.params._ComparisonEndMsec[self.channel]) / 1000
        MMeanRect = self.ResponseMagnitudes(data=Data,interval=(ind1,ind2),fs=self.parent.fs,lookback=self.parent.lookback,p2p=False)
        #(NewMwin, NewHwin) = self.CalculateWindows(Data)

        #Pool and correct currents here
        (A, C) = Pool(numpy.array([HAmplitudes,MAmplitudes,BGAmplitudes,MMeanRect]),Currents,Pooling)

        # Reorder A,C
        (A, C) = Reorder(C,A)

        HAmpsPooled = A[0,:].tolist(); MAmpsPooled = A[1,:].tolist();  BGAmpsPooled = A[2,:].tolist(); MMeanRectPooled = A[3,:]

        #Find Hmax - not just the max but something that matches a criterion for Hmax
        CurrentHmax = self.FindHmax(HAmpsPooled,BGAmpsPooled,C)

        #Find H threshold (need this as we may have different thresholds in different muscle groups)
        CurrentHthreshold = self.Threshold(HAmpsPooled,C,BGAmpsPooled)
        #m1 = MAmpsPooled[0]
        #CurrentMthreshold = self.Threshold([m-m1 for m in MAmpsPooled], C, BGAmpsPooled) #offset from first stim in case of stim artefact effects
        CurrentMthreshold = self.Threshold(MAmpsPooled, C, BGAmpsPooled)

        #returning (Usability, Optimal Current,  Gradient, Min of Range, Max of Range, M amplitude to work with, M rectified value at current
        if (CurrentHmax == -1) or (CurrentHthreshold == -1) or (CurrentMthreshold == -1): return (-1,0,0,0,0,0)
        else:
            #So we want the current to be between Hthreshold and Hmax (ideally)
            if (CurrentMthreshold > CurrentHmax): return (-1,0,0,0,0,0) #unusable
            elif (CurrentMthreshold > CurrentHmax*0.95):
                gM = numpy.gradient(numpy.array(MMeanRectPooled))
                #Limits = (CurrentMthreshold,CurrentHmax)
                indx = [i == CurrentMthreshold for i in C].index(True)
                if indx < 0: indx = 0
                return (0,CurrentMthreshold,gM[indx],CurrentMthreshold,CurrentHmax,MMeanRectPooled[indx]) #usable but not ideal
            elif CurrentMthreshold > CurrentHthreshold:
                HMC50pc = ((CurrentHmax*0.9 - CurrentMthreshold) / 4) + CurrentMthreshold
                #extract the new estimated M target and the new gradient
                (gM,Mtarget) = CalculateMtarget(MMeanRectPooled,C,HMC50pc)
                #Limits = (CurrentMthreshold, CurrentHmax*0.9)
                return (1, HMC50pc, gM,CurrentMthreshold, CurrentHmax*0.95,Mtarget)  # If greater than the threshold and does not meet the other criteria we take which is greater (50%,Mthreshold)
            else:
                HC50pc = ((CurrentHmax*0.9 - CurrentHthreshold*1.1) / 4) + (CurrentHthreshold*1.1)
                # extract the new estimated M target and the new gradient
                (gM, Mtarget) = CalculateMtarget(MMeanRectPooled,C,HC50pc)
                #Limits = (CurrentHthreshold*1.1, CurrentHmax*0.9)
                return (1, HC50pc, gM,CurrentHthreshold, CurrentHmax*0.95,Mtarget)  # Meant Mthreshold is <= CurrentHthreshold, so we have a lot to play with

    def BestRC(self):
        """
        From RCStorage determine the best Recruitment Curve
        """

        G = numpy.array(self.parent.stimGUI.RCStorage['grad'])  # Gradient at Stim Current
        U = numpy.array(self.parent.stimGUI.RCStorage['use'])  # Gradient at Stim Current
        # Best position is where we have a useable current and has the highest M-gradient
        D = numpy.array(U)  # This variable will tell us which is the best current

        indD = numpy.where(D == 1)[0]

        if indD.size > 0:
            ind = indD[numpy.where(G[indD] == numpy.max(G[indD]))]
            D[indD] = 0; D[ind] = 1

        return D.tolist()

    def CalculateWindows(self,Data):
        """
        Automatically calculate the smallest M and H windows that do not affect the M and H RMS amplitude
        """

        #Input is raw data

        Mwin = (float(self.parent.operator.params._ComparisonStartMsec[self.channel]) / 1000,float(self.parent.operator.params._ComparisonEndMsec[self.channel]) / 1000)
        Hwin = (float(self.parent.operator.params._ResponseStartMsec[self.channel]) / 1000,float(self.parent.operator.params._ResponseEndMsec[self.channel]) / 1000)
        Di = numpy.sum(numpy.asarray(Data),0)

        NewMwin = self.RefineWindows(Di, Mwin)
        NewHwin = self.RefineWindows(Di, Hwin)

        return NewMwin, NewHwin

    def RefineWindows(self,Data, ind):
        """
        Refine the M or H windows - called by CalculateWindows
        """
        # Challenge with the FCR
        # With Soleus we can just narrow until the mean rectified does not change by >10%
        # What do we do with FCR? - Issues of the overlap between M and H, and Stim and M
        # So here we take the current H and M window, calculate the MeanRectified, adjust the window until MeanRectified does not vary by more than 10%

        def MeanRectified(x):
            x_mean = sum(x) / len(x)
            return sum([abs(i - x_mean) for i in x]) / float(len(x))

        newInd = [ind[0], ind[1]]
        #xMR = MeanRectified([Data[i - 1] for i in range(ind[0], ind[1] + 1)])
        xMR = self.ResponseMagnitudes(data=Data.tolist(), interval=(ind[0], ind[1]), fs=self.parent.fs, lookback=self.parent.lookback,p2p=False,SingleTrial=True)

        N = 0.001
        NoChange = 1

        while NoChange == 1:
            x = self.ResponseMagnitudes(data=Data.tolist(), interval=(ind[0], ind[1] - N), fs=self.parent.fs, lookback=self.parent.lookback,p2p=False,SingleTrial=True)
            #x = MeanRectified([Data[i - 1] for i in range(ind[0], ind[1] - (N - 1))])
            if 100 * abs(1 - (x[0] / xMR[0])) > 5:
                newInd[1] = round(ind[1] - N + 0.001,5)
                NoChange = 0
            else:
                N += 0.001

        N = 0.001
        NoChange = 1
        #xMR = MeanRectified([Data[i - 1] for i in range(ind[0], newInd[1])])
        xMR = self.ResponseMagnitudes(data=Data.tolist(), interval=(ind[0], newInd[1]), fs=self.parent.fs,lookback=self.parent.lookback, p2p=False,SingleTrial=True)
        while NoChange == 1:
            x = self.ResponseMagnitudes(data=Data.tolist(), interval=(ind[0]+N, newInd[1]), fs=self.parent.fs,lookback=self.parent.lookback, p2p=False,SingleTrial=True)
            #x = MeanRectified([Data[i - 1] for i in range(ind[0] + (N), newInd[1])])
            if 100 * abs(1 - (x[0] / xMR[0])) > 5:
                newInd[0] = round(ind[0] + N - 0.001,5)
                NoChange = 0
            else:
                N = N + 0.001

        return newInd

class StimControl(object):
    """
    A heuristic control method for controlling the current during CT and TT

    At present it is a function of the moving average difference and moving average of the value compared to the setpoint
    """

    def __init__(self,Setpoint,Gradient,N=3):
        if False:
            self.N = N #Lookback length, number of samples to use for heuristic controller
            self.Setpoint = Setpoint # target
            self.Gradient = Gradient # NOT used
            self.x = numpy.array([]) # array of values
            self.error = numpy.array([])
            self.delta = numpy.array([0])
            
        else:
            
                    self.Setpoint = numpy.fromstring(row[0],dtype=float,sep=' ')# target
                    self.initial = numpy.fromstring(row[1],dtype=float,sep=' ')					
                    self.beta = numpy.fromstring(row[2],dtype=float,sep=' ') # derivative control filtering parameter
            self.error = numpy.array([]) # array of errors
            self.integ = numpy.array([0]) # array of error integral values
            self.deriv = numpy.array([0]) # array of error derivative values
            self.output_history = numpy.array([0]) # array of output history
            self.Kp = -0.001 # proportional control gain
            self.Ki = -0.001 # integral control gain
            self.Kd = -0.001 # derivative control gain
            # self.alpha = 1 # control tuning parameter
            # self.Kp = -self.alpha*self.beta**2/(1-self.beta)**2 # proportional control gain
            # self.Ki = self.alpha/(1-self.beta) # integral control gain
            # self.Kd = self.alpha*self.beta**2/(1-self.beta)**3 # derivative control gain
        
    def Update(self,NewValue):
        """
        Based on the new M-wave amplitude we recalculate the next current (called by CTTTProcess
        
        """



        if False:
            #input is a series of values i-N+1:i
            self.x = numpy.append(self.x,[100*(NewValue-self.Setpoint)/self.Setpoint]) # percent error from setpoint, think of this as being a quasi proportion control paramter
            l = numpy.size(self.x) # number of trials so far

            if l > 1: # for trial 2 to end
                # we can think of the delta as a quasi derivative control
                self.delta = numpy.append(self.delta,  self.x[l-1]-self.x[l-2]) # difference in x from one trial to the next, are we getting closer to setpoint or farther away?
            #else: self.delta = numpy.append(self.delta, self.x[l - 1] - self.Setpoint)

            ind1 = range(max(0,l-self.N+1),l) # get indices for last N-1 trials with some constraints to prevent errors (max)
            ind2 = range(max(0,l-self.N),l) # get indices for last N trials with some constraints to prevent errors (max)
            output = (numpy.mean(self.delta[ind1]) + numpy.mean(self.x[ind2])) / 2 # take mean of derivative control over last N-1 samples + mean of proportional control over N samples and divide by two

            #we allow for a 10% variation
            if abs(output) < 10: output = 0

            return -1*output
        
        else:
            NewValue = NewValue * 1000 # rescale from volts to mv
            current_error = NewValue-self.Setpoint # find current error
            self.error = numpy.append(self.error,[current_error]) # append current error to array of errors

            l = numpy.size(self.error) # number of trials so far
            if l == 1:
                output = self.initial
                self.output_history = numpy.append(self.output_history,[output])				
                return output

            if l>1:
                current_deriv = self.beta*self.deriv[-1]+(1-self.beta)*(self.error[-1]-self.error[-2]) # find current error derivative
                current_integ = self.integ[-1]+self.error[-2] # find current error integral

                self.deriv = numpy.append(self.deriv,[current_deriv]) # append current error derivaitve to array of error derivatives
                self.integ = numpy.append(self.integ,[current_integ]) # append current error integral to array of error integrals

            # output = self.Kp*self.error[l-1]+self.Ki*self.integ[l-1]+self.Kd*self.deriv[l-1] # PID controller
            output = self.output_history[-1] + (self.Ki-2*self.Kp+self.beta*self.Kp)*self.error[-2] + (2*self.Kp-self.beta*self.Kp)*self.error[-1] - self.Kd*self.deriv[-2] + self.beta*self.Kd*self.deriv[-1] # recursive PID controller
            self.output_history = numpy.append(self.output_history,[output]) # append current error to array of errors

            print('New Value * 1000 ',NewValue)
            print('Controller Output - ',output)
            print('Error - ',current_error)
            print('Previous Output - ',self.output_history[-2])
            return output


class D188Control(tkinter.Toplevel):

    """
    The Digitimer D188 is a tool for multiplexing the stimulation

    Here are are setting up some basic controls.
    In the new BCI2000 files it is a state called: D188Channel which is added to the FilterExpressions
    It is an 4bit number - i.e. 0001 is channel 1, 0010, channel 2 and 1000 channel 8
    """

    def __init__(self,parent,statename="D188Channel",minValue=1,maxValue=8):

        self.parent = parent
        self.operator = parent.operator
        self.statename = statename
        self.minValue = minValue
        self.maxValue = maxValue
        self.widgets = Bunch()
        self.Channel = tkinter.StringVar()
        self.Initialize()


        if not hasattr(self.parent,'stimGUI'):
            tkinter.Toplevel.__init__(self)
            self.wm_title('Dl88 Channel')
            # self.wm_geometry('225x150')
            self.wm_resizable(width=False, height=False)
            # self.wm_attributes("-topmost", 1)
            # self.withdraw()
            Frame=None
        else:
            Frame = self.parent.stimGUI.header

        self.CreateWindow(header=Frame)

        return

    def Initialize(self):
        """
        Initialize some key variables

        Needed to reset these when starting a new ST run
        """

        self.ChannelsUsed = []
        self.CurrentChannel = int(self.parent.operator.remote.GetParameter('InitialD188Channel'))
        ### D188Channel will be the one selected for RC etc.
        self.D188Channel = self.CurrentChannel
        self.Channel.set(self.CurrentChannel)
        self.direction = -1 #-1=down, 1=up
        self.Multipler = 2
        self.ResponseFound = False
        self.First=1

        #Internal data that let's us know what the threshold was and amplitude for each channel - note having a response should be inherent in these values
        self.Data = Bunch(Channel=range(1,8,1), Hthreshold=[0,0,0,0,0,0,0,0],Hamplitude=[0,0,0,0,0,0,0,0],Signal=[[],[],[],[],[],[],[],[]],ResponseFound=[0,0,0,0,0,0,0,0])

    def CreateWindow(self,header=None):

        """
        Embeds channel control into the Stimulation Control Panel (CurrentControl) if it exists
        """

        if header == None: header = tkinter.Frame(self, bg='white')

        self.widgets.LabelFrame = w = tkinter.LabelFrame(header, bg='white',text='Channel:', padx=5, pady=5)

        fontMED = ('Helvetica', 18)
        self.Label = tkinter.Spinbox(w, font=fontMED, from_=1, increment=1,to=8,bg='white', width=5, textvariable=self.Channel)
        self.Label.grid(row=2, column=0, padx=3, pady=5, sticky='ew')
        self.Channel.trace('w', self.SetChannel)
        self.Label.config(state='readonly')

        w.grid(row=0, column=3, rowspan=3, padx=5, pady=5, sticky='nsew')
        header.pack(side='top', fill='both', expand=1)

    def DestroyWindow(self):
        self.widgets.LabelFrame.grid_forget()
        self.parent.stimGUI.header.pack(side='top', fill='both', expand=1)

    def SetChannel(self,in1=None,in2=None,in3=None,Value=None):
        """
        Sets the current D188 channel either via the BCI2000 state D188Channel or via the parameter InitialD188Channel
        """

        if Value==None:        Value = int(self.Channel.get())

        def ValidateValue(Value):
            if Value >= self.minValue and Value <= self.maxValue: return True
            else: return False

        if ValidateValue(Value):
            if self.parent.operator.started:
                self.operator.bci2000('Set State '+ self.statename + ' ' + str(Value))
            else:
                self.parent.operator.bci2000('Set Parameter InitialD188Channel ' + str(Value))

        self.Channel.set(str(Value))
        self.parent.operator.needSetConfig = True

        return

    def GuidanceWindow(self,MainQuestion,InputOptions):
        """
        For future use ti guide how the stimulus feels for a user and make sure other muscles and/or nerves are being stimulated
        """

        #MainQuestions - Main Question to ask the user
        #InputOptions - List of buttons and text
        #return option selected

        self.top = Top = tkinter.Toplevel()
        fontlarge = ('Helvetica', 14)
        self.GroupButtons = []
        #Top.title(MainQuestion)

        subFrame = tkinter.LabelFrame(Top, text=MainQuestion, padx=5, pady=5, font=fontlarge)

        for i in range(len(InputOptions)):
            w = tkinter.Button(subFrame, text=InputOptions[i], command=lambda x=i: self.SelectButton(val=x))
            w.grid(row=1, column=i, sticky='ew', pady=5,padx=5)
            self.GroupButtons.append(w)

    def SelectButton(self,val):
        """
        Paired with Guidance Window
        """

        self.Selection = val
        self.top.destroy()

    def StoreChannelData(self,Channel,Hamp,Hth,Signal):
        """
        Store information about which D188 channel is being used
        :param Channel: Channel number
        :param Hamp: Amplitude of H at threshold
        :param Hth: H threshold
        :param Signal: Raw trial data
        """

        self.Data["Hamplitude"][Channel - 1] = Hamp
        self.Data["Hthreshold"][Channel - 1] = Hth
        self.ChannelsUsed.append(Channel)
        self.Data["Signal"][Channel - 1] = Signal

        return

    def ChannelSelection(self,Channel,Response,Hamp,Hth):
        """
        Determine which channel to go to next

        Assuming that we have 8 channels (the D188 has 8) then we are cycling through to find a spot with a response and
        the one with the lowest Hthreshold

        """

        #Response is whether an H was found or not
        #Hamp is it's peak-peak amplitude at Hth
        #Hth is the H threshold

        #Warning here - we assume the main function that will drive this: CurrentControl  has already assigned the values in StoreChannelData
        #If you are getting strange results then check this is happening first

        #Function uses self.CurrentChannel, self.NextChannel and self.PreviousChannel to determine where to go next. Initially there is no NextChannel or PrevChannel

        # Two criteria that this is a better channel: lower Hth and larger Hamp at Hth if the same (roughly)
        if self.ResponseFound:
            Criteria1 = Hth < 0.95*self.Data["Hthreshold"][self.CurrentChannel-1]
            Criteria2 = Hamp > self.Data["Hamplitude"][self.CurrentChannel-1]
        else: Criteria1 = Criteria2 = True

        if Response:
            self.ResponseFound = True
            self.Data["ResponseFound"][self.CurrentChannel - 1] = 1

        if not self.First:

            if not self.ResponseFound and not Response:
                self.direction = self.direction*-1
                self.Multipler = self.Multipler*2
                NewChannel = Channel + self.Multipler * self.direction
            else:
                if Response and Criteria1 and Criteria2:
                    #This becomes our best channel
                    self.CurrentChannel = Channel
                    self.D188Channel = Channel

                #Check if we have looked at either side channel
                if self.D188Channel-1 in self.ChannelsUsed:
                    if self.D188Channel+1 in self.ChannelsUsed:
                        NewChannel = -1
                    else: NewChannel = self.D188Channel+1
                else: NewChannel = self.D188Channel-1
        else:
            if Response:
                NewChannel = Channel + self.direction
                self.ResponseFound = True
            else:
                NewChannel = Channel + self.Multipler*self.direction
            self.First = 0

        if NewChannel != -1:
            if NewChannel < 1: NewChannel = 1
            if NewChannel > 8: NewChannel = 8

            self.CurrentChannel = NewChannel

        if NewChannel in self.ChannelsUsed:
            return -1
        else:
            return NewChannel

    def FinalChannelSelection(self):
        """
        Determine the best D188 channel from the data
        """

        Hth = numpy.array(self.Data["Hthreshold"])
        Hamp = numpy.array(self.Data["Hamplitude"])

        try:
            hx = numpy.min(Hth[numpy.nonzero(Hth)])
            hi = numpy.where(Hth == hx)
            hbest = hi[0][numpy.where(Hamp[hi[0]] == numpy.max(Hamp[hi[0]]))[0]].tolist()[0]+1
        except:
            hbest = -1

        self.SetChannel(Value=hbest)
        self.Label['state'] = 'normal'
        self.D188Channel = hbest

        self.PopulateStimLocations()

        return hbest

    def PopulateStimLocations(self):
        """
        Function populates the fields for StimLocations to be used in the preRCStart
        """
        #self.parent.stimGUI.StimLocations = OrderedDict()
        for i in range(0, 8):
            if self.Data["ResponseFound"][i] == 1: self.parent.stimGUI.addLocation(val="Channel" + str(i + 1),value1=self.Data["Hthreshold"][i],value2=self.Data["Hamplitude"][i])





