#
#
# This script is intended to create the keys in hdbuserstore for HANA Non-MDC and HANA MDC, Single Node
# Author: Catalin Mihai Popa -> i324220
#
#
import os, subprocess, shutil, datetime
from datetime import datetime


class HdbUserStoreClass():
    def createHdbUserStoreForHANAMDC(self):
        print()

    def createHdbUserStoreForHANANonMDC(self):
        print()

    def checkifHANA_NonMDC_MDC(self):

        output = subprocess.check_output(['hdbnsutil -printSystemInformation'], shell=True).splitlines(1)

        for line in output:
            if "SingleDB" in line:
                self.is_mdc = False
                dateexecution = datetime.now()
                print(dateexecution.strftime("Date and time when the script was executed: %x, %H:%M"))
                print(self.is_mdc)

            else:
                if "MultiDB" in line:
                    self.is_mdc = True
                    dateexecution = datetime.now()
                    print(dateexecution.strftime("Date and time when the script was executed: %x, %H:%M"))
                    print(self.is_mdc)

def main():
    # process = subprocess.Popen(['hdbnsutil', '-printSystemInformation'], stdout=subprocess.PIPE)
    # outCheckHana_NonMDC_MDC = process.communicate()[0]
    husc = HdbUserStoreClass()
    husc.checkifHANA_NonMDC_MDC()

if __name__ == '__main__':
    main()