import clr, sys
import tkMessageBox
import time,os, inspect

path =  os.path.dirname(os.path.realpath(inspect.getfile(inspect.currentframe())))
sys.path.append(path)
InteropDirectory = os.path.abspath( os.path.join(path,'../'))
dllpath = os.path.join(InteropDirectory,"Interop.DS5Lib.dll")
clr.AddReference(dllpath)

import DS5Lib

class DS5LibClass(object):

    def __init__(self,DS5_BCI2000_parameter=False):

        self.DS5_BCI2000_enabled = DS5_BCI2000_parameter
        self.DS5init = False

        if self.DS5_BCI2000_enabled:
            self.CheckDS5Connected()
        if self.DS5init:
            self.Set5mA5V()

    def CheckDS5Connected(self):
        try:
            application = DS5Lib.Application()
            devices = application.Devices()
            devices = DS5Lib.ICollection(devices)
            time.sleep(0.1)
            self.device = DS5Lib.Device(devices.get_Item(0))
            self.DS5init = True
        except:
            try:
                application = DS5Lib.Application()
                devices = application.Devices()
                devices = DS5Lib.ICollection(devices)
                time.sleep(0.1)
                self.device = DS5Lib.Device(devices.get_Item(0))
                self.DS5init = True
            except:
                tkMessageBox.showinfo('DS5', 'DS5 not connected. Please check power and connections.')
                self.DS5init = False

    def AutoZero(self):
        self.CheckDS5Connected()
        param = DS5Lib.ControlClass()
        param.AutoZero = True
        self.device.Control = param

    def ToggleOutput(self,OnOff=False):
        self.CheckDS5Connected()
        param = DS5Lib.ControlClass()

        if OnOff:
            param.OutputEnable = True
        else:
            param.OutputEnable = False

        self.device.Control = param

    def Set5mA5V(self):
        param = DS5Lib.ControlClass()
        param.InputVoltageRange = DS5Lib.EnInputVoltageRange.enIVR5V0;
        param.OutputCurrentRange = DS5Lib.EnOutputRange.enOR50mA;
        self.device.Control = param;



#DS5 = DS5LibClass(DS5_BCI2000_parameter=True)

#time.sleep(0.5)
#DS5.AutoZero()
#time.sleep(0.5)
#DS5.ToggleOutput(OnOff=True)
