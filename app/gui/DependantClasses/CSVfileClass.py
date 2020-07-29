import csv

class CSVfileClass(object):

    def __init__(self,FileName,HeaderLabels,HeaderValues,DataLabels,Data,parent=None):

        oFile = open(FileName+'.csv', 'wb')
        self.writer = csv.writer(oFile)

        self.ConstructHeaders(HeaderLabels,HeaderValues)
        self.WriteData(DataLabels,Data)

        oFile.close()


    def ConstructHeaders(self,Labels,Values):

        #for l,v in (Labels, Values):
        #    self.writer.writerow([l+': '+str(v)])

        for i, l in enumerate(Labels):
            line = []
            line.append(l+": ")
            if type(Values[i])==list:
                line = line + Values[i]
            else: line.append(str(Values[i]))
            self.writer.writerow(line)

    def WriteData(self,Labels,Data):

        self.writer.writerow(Labels)

        for d in Data:
            self.writer.writerow(d)