#
#
# This script is intended to create the keys in hdbuserstore for HANA Non-MDC and HANA MDC, Single Node
#
#
import subprocess, os, sys


# from datetime import datetime

class HdbUserStoreClass:

    def getparameters(self):
        output = subprocess.check_output('HDB info', shell=True).splitlines(1)
        print(output)

    def createhdbuserstorehanamdc(self):
        print()

    def createhdbuserstorehananonmdc(self):
        print()


def main():
    output = subprocess.check_output('HDB info', shell=True).splitlines(1)
    subprocess.call(["echo","hello"])
    subprocess.call(['echo',output])
    if __name__ == "__main__":
        main()
