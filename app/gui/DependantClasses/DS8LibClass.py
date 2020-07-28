### CLASS TO CONTROL DS8 VIA PYTHON
from ctypes import *
import os, inspect,sys

path =  os.path.dirname(os.path.realpath(inspect.getfile(inspect.currentframe())))
sys.path.append(path)
DLLDirectory = os.path.abspath( os.path.join(path,'../'))
dllpath = os.path.join(DLLDirectory,"DS8library.dll")

DS8 = cdll.LoadLibrary(dllpath)

class DS8Functions(object):

    def __init__(self):
        DS8.DS8_new.argtypes = [c_void_p]
        DS8.DS8_new.restypes = c_void_p

        DS8.DS8_initialise.argtypes = [c_void_p]
        DS8.DS8_initialise.restypes = c_int

        DS8.DS8_ToggleOutput.argtypes = [c_void_p,c_bool]
        DS8.DS8_ToggleOutput.restypes = c_void_p

        DS8.DS8_set.argtypes = [c_void_p,c_int,c_int,c_int,c_int,c_int,c_int,c_bool]
        DS8.DS8_set.restypes = c_void_p

        DS8.DS8_close.argtypes = [c_void_p]
        DS8.DS8_close.restypes = c_void_p

        self.obj = DS8.DS8_new(None)

    def Initialise(self):
        """
        ErrorCodes:
        0 OK;
        1 DGD128_Initialise failed;
        2 DGD128_Update failed;
        3 DGD128_Close failed;
        4 Could not load D128API.DLL;
        5 retError or retAPIError;
        6 Could not extract current state;
        7 No DS8s found
        """
        return DS8.DS8_initialise(self.obj)

    def Toggle(self,val):
        return DS8.DS8_ToggleOutput(self.obj,val)

    def Set(self,mode, polarity, current, width,recovery, dwell,update):
        DS8.DS8_set(self.obj, mode,polarity, current, width,recovery, dwell,update)

    def Close(self):
        DS8.DS8_close(self.obj)


# f = DS8Functions()
# i = f.Initialise()
# f.Set(2,2,100,500,100,1,True)
# f.Toggle(True)
#
# time.sleep(1)
#
# f.Toggle(False)
# f.Close()

