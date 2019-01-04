#######################################
# This script is intended to create the keys in HDBuserstore for HANA Non-MDC and HANA MDC - single node
# Author: Catalin Mihai Popa -> i324220
######################################

import os, subprocess, datetime
from datetime import datetime


class HDBUserStoreClass(object):

    def __init__(self):
        self.is_mdc = False

    @staticmethod
    def obtain_parameters():

        sapsystemname = subprocess.check_output('echo $SAPSYSTEMNAME', shell=True).replace('\n', '')
        os.chdir(r"/hana/shared/" + sapsystemname + r"/profile/")
        profilename = subprocess.check_output('ls | egrep "(.*)_(.*)_(.*)"', shell=True).replace('\n', '')
        print(profilename)

        dparameters = {'systemdbsid': subprocess.check_output('echo $SAPSYSTEMNAME', shell=True).replace('\n', ''),
                       'tenantsid': subprocess.check_output("hdbnsutil -printSystemInformation | awk -v c=1 'NR==4 {print $c}'", shell=True).replace('\n', ''),
                       'systemdbsqlport': subprocess.check_output("hdbnsutil -printSystemInformation | awk -v c=4 'NR==3{print $c}' | grep -o '.....$'", shell=True).replace('\n', ''),
                       'tenantsqlport': subprocess.check_output("hdbnsutil -printSystemInformation | awk -v c=2 'NR==4 {print $c}' | grep -o '.....$'", shell=True).replace('\n', ''),
                       'localhostname': subprocess.check_output("less " + profilename + ' | grep "SAPLOCALHOST = " ' + "| grep -o '............$'", shell=True).replace('\n','')}

        print("#################################Parameters to be used in HDBuserstore keys creation#################################")
        for k, v in dparameters.iteritems():
            print('Parameter name: {} -> {}'.format(k, v))
        print("#####################################################################################################################")

        return dparameters

    @staticmethod
    def create_hdb_user_store_hana_mdc():
        dparameters = HDBUserStoreClass.obtain_parameters()

        wsidkey = 'hdbuserstore SET W{} "{}:{}" SYSTEM U1c_smpo4B'.format(dparameters.get('tenantsid'), dparameters.get('localhostname'), dparameters.get('tenantsqlport'))

        subprocess.call([wsidkey], shell=True)

        subprocess.call(['hdbuserstore list'], shell=True)

    @staticmethod
    def create_hdb_user_store_hana_non_mdc():

        print("HANANonMDC")
        dparameters = HDBUserStoreClass.obtain_parameters()

    def check_hana_type(self):
        output = subprocess.check_output(['hdbnsutil -printSystemInformation'], shell=True).splitlines(1)

        for line in output:
            if "SingleDB" in line:
                self.is_mdc = False
                date_execution = datetime.now()
                print(date_execution.strftime("Date and time when the script was executed: %x, %H:%M"))
                print("HANA is Non-MDC")

            else:
                if "MultiDB" in line:
                    self.is_mdc = True
                    date_execution = datetime.now()
                    print(date_execution.strftime("Date and time when the script was executed: %x, %H:%M"))
                    print("HANA is MDC")

        if self.is_mdc:
            HDBUserStoreClass.create_hdb_user_store_hana_mdc()
        else:
            HDBUserStoreClass.create_hdb_user_store_hana_non_mdc()

def main():

    oh = HDBUserStoreClass()
    oh.check_hana_type()

if __name__ == '__main__': main()