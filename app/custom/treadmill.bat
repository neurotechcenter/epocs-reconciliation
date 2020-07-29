
# add the auxiliary FOOT switch signal as a fourth channel

SET PARAMETER     Source        int        SourceCh=                   4
SET PARAMETER     Source        floatlist  SourceChOffset=             4     0         0         0         0     
SET PARAMETER     Source        floatlist  SourceChGain=               4   162.07    162.07    162.07    162.07   // TODO: NB: this will have to be calibrated for each setup. Also calibration not yet verified for channels that go through the AMT-8 amp
SET PARAMETER     Source        list       ChannelNames=               4   EMG1      EMG2      TRIG      FOOT     // 
SET PARAMETER     Trigger       list       ChannelsToTrap=             2   EMG1      EMG2      TRIG      FOOT     // names or indices of the input channels to be trapped

