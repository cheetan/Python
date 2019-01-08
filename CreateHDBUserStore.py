#######################################
# This script is intended to create the keys in HDBuserstore for HANA Non-MDC and HANA MDC - single node
# Author: Catalin Mihai Popa -> i324220
######################################

import os, subprocess, datetime
from datetime import datetime


class HDBUserStoreClass(object):

    def __init__(self):

        hana_type = subprocess.check_output(['hdbnsutil -printSystemInformation'], shell=True).splitlines(1)
        for line in hana_type:
            if "SingleDB" in line:
                self.is_mdc = False
                date_execution = datetime.now()
                print(date_execution.strftime("Date and time when the script was executed: %x, %H:%M"))
                print("\n\n\n")
                print("################################# \tPrint HANA Type \t#################################")
                print("HANA is Non-MDC")
                print("#################################################################################")
                print("\n\n\n")
            else:
                if "MultiDB" in line:
                    self.is_mdc = True
                    date_execution = datetime.now()
                    print(date_execution.strftime("Date and time when the script was executed: %x, %H:%M"))
                    print("\n\n\n")
                    print("################################# \tPrint HANA Type \t#################################")
                    print("HANA is MDC")
                    print("#################################################################################")
                    print("\n\n\n")

        sap_system_name = subprocess.check_output('echo $SAPSYSTEMNAME', shell=True).replace('\n', '')
        os.chdir(r"/hana/shared/" + sap_system_name + r"/profile/")
        profile_name = subprocess.check_output('ls | egrep "(.*)_(.*)_(.*)"', shell=True).replace('\n', '')

        self.dparameters = {'systemdbsid': subprocess.check_output('echo $SAPSYSTEMNAME', shell=True).replace('\n', ''),
                            'tenantsid': subprocess.check_output("hdbnsutil -printSystemInformation | awk -v c=1 'NR==4 {print $c}'", shell=True).replace('\n', ''),
                            'systemdbsqlport': subprocess.check_output("hdbnsutil -printSystemInformation | awk -v c=4 'NR==3{print $c}' | grep -o '.....$'", shell=True).replace('\n', ''),
                            'tenantsqlport': subprocess.check_output("hdbnsutil -printSystemInformation | awk -v c=2 'NR==4 {print $c}' | grep -o '.....$'", shell=True).replace('\n', ''),
                            'localhostname': subprocess.check_output("less " + profile_name + ' | grep "SAPLOCALHOST = " ' + "| grep -o '............$'", shell=True).replace('\n', '')}

        os.chdir(r"/hana/shared/" + sap_system_name + r"/global/hdb/custom/config")

        self.dparameters['master_hosts'] = subprocess.check_output("""awk '$1 == "master" {for(i=3; i<=NF; i++) print substr($i,1,12)}' nameserver.ini""", shell=True).split()

        print("#################################\tParameters to be used in HDBuserstore keys creation\t#################################")
        for k, v in self.dparameters.iteritems():
            print('Parameter name: {} -> {}'.format(k, v))
        print("#####################################################################################################################")

        if len(self.dparameters['master_hosts']) > 1:
            self.is_multi_node = True
        else:
            self.is_multi_node = False

        replication_process = subprocess.Popen(['hdbnsutil', '-sr_state'], stdout=subprocess.PIPE)
        out = replication_process.communicate()

        self.has_replication = True if "active primary site" in out else False

    def create_hdb_user_store_hana_mdc(self):

        print("HANAMDC")
        # wsidkey = 'hdbuserstore SET W{} "{}:{}" SYSTEM U1c_smpo4B'.format(dparameters.get('tenantsid'), dparameters.get('localhostname'), dparameters.get('tenantsqlport'))
        #
        # subprocess.call([wsidkey], shell=True)
        #
        # subprocess.call(['hdbuserstore list'], shell=True)

    def create_hdb_user_store_hana_non_mdc(self):

        print("HANANonMDC")


def main():
    ohana = HDBUserStoreClass()

    if ohana.is_mdc:
        ohana.create_hdb_user_store_hana_mdc()
    else:
        ohana.create_hdb_user_store_hana_non_mdc()


if __name__ == '__main__': main()