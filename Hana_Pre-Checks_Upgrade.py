############################################################################
# This script is intended to perform the pre-checks for HANA Non-MDC and MDC upgrade
# Author: Catalin Mihai Popa -> I324220
# Used Facade structural pattern
# Used Singleton creational pattern
############################################################################

import sys
import os
import glob
import getpass
import subprocess
from datetime import datetime, timedelta
import re
import logging

BACKINT_MODULE = 821
BACKINT_BUILD = 773


class Borg:
    """Borg class making class attributes global"""
    _shared_parameters = {}  # Parameter dictionary

    def __init__(self):
        self.__dict__ = self._shared_parameters  # Make it an attribute dictionary


class ParameterManagerSingleton(Borg):
    """This class now shares all its attributes among its various instances"""

    def __init__(self, system_password):
        Borg.__init__(self)
        self._shared_parameters.update(system_pwd=system_password)
        self._shared_parameters.update(sid=os.getenv("SAPSYSTEMNAME"))
        self._shared_parameters.update(
            instance_number=os.getenv("DIR_INSTANCE")[-2:])

    def __str__(self):
        return str(self._shared_parameters)


class HanaChecksSingleton(Borg):
    """This class now shares all its attributes among its various instances"""

    def __init__(self):
        Borg.__init__(self)
        self._shared_parameters.update(
            hana_version=subprocess.check_output(
                "HDB version | grep version: | awk -F ' ' '{print $2}'",
                shell=True).replace("\n", ""))
        if re.findall(r'^2', self._shared_parameters['hana_version']):
            self._shared_parameters.update(hana_type='MDC')
        else:
            self._shared_parameters.update(hana_type='Non-MDC')
        if self._shared_parameters['hana_type'] == 'MDC':
            self._shared_parameters.update(
                sql_connection_string="hdbsql -i " +
                self._shared_parameters['instance_number'] +
                " -A -j -x -u SYSTEM -n localhost:3" +
                self._shared_parameters['instance_number'] +
                "13 -p " + self._shared_parameters['system_pwd'])
        else:
            self._shared_parameters.update(
                sql_connection_string="hdbsql -i " +
                self._shared_parameters['instance_number'] +
                " -A -j -x -u SYSTEM -p " +
                self._shared_parameters['system_pwd'])
        os.chdir(
            r"/hana/shared/" + self._shared_parameters['sid'] + r"/global/hdb/custom/config")
        master_list = subprocess.check_output(
            """awk '$1 == "master" {for(i=3; i<=NF; i++) print substr($i,1,12)}' nameserver.ini""",
            shell=True).split()
        if len(master_list) < 2:
            self._shared_parameters.update(is_multi_node=False)
            self._shared_parameters.update(hostname=master_list[0])
        else:
            self._shared_parameters.update(is_multi_node=True)
            for i, v in enumerate(master_list, start=1):
                node = {"master_" + str(i): v}
                self._shared_parameters.update(node)

    def __str__(self):
        return str(self._shared_parameters)

    def check_hana_services(self):

        check = True
        if self._shared_parameters['is_multi_node']:
            hs = "sapcontrol -nr " + self._shared_parameters['instance_number'] + \
                " -function GetSystemInstanceList | grep hdb | awk -F ',' '{print $7}'"
            hana_services_status = (
                subprocess.check_output(hs, shell=True).replace(" ", "").split())
        else:
            hs = "sapcontrol -nr " + \
                self._shared_parameters['instance_number'] + \
                " -function GetProcessList | grep hdb | awk -F ',' '{print $3}'"
            hana_services_status = (
                subprocess.check_output(hs, shell=True).replace(" ", "").split())
        for status in hana_services_status:
            check = False if status != "GREEN" else True

        if check:
            print("\033[1;32m All HANA services are in GREEN state \n")
            print("\033[0m")
        else:
            print("\033[1;31m Not all HANA services are in GREEN state \n")
            print("\033[0m")

    def check_hana_replication(self):

        possible_hana_replication_modes = {
            "none": False, "primary": True, "sync": True, "syncmem": True, "async": True}
        hana_replication_mode = subprocess.check_output(
            """hdbnsutil -sr_state | grep mode: | awk -F ' ' '{print $2}' | head -1""",
            shell=True)
        check = possible_hana_replication_modes.get(
            hana_replication_mode, False)
        if check:
            print("\033[1;33m Database has replication enabled \n")
            print("\033[0m")
        else:
            print("\033[1;32m Database is not configured for replication \n")
            print("\033[0m")

    def check_hana_plugins(self):

        try:
            os.chdir(r"/usr/sap/" + os.getenv("SAPSYSTEMNAME") +
                     r"/SYS/exe/hdb/plugins")
            print("\033[1;33m Plugins are installed on the database")
            print("\033[1;33m Plugins that have been detected: \n")
            plugins_list = os.listdir('.')
            for plugin in plugins_list:
                print("\t" + plugin)
            print("\033[0m")
        except OSError:
            print("\033[1;32m There are no plugins installed \n")
            print("\033[0m")

    def get_hana_version(self):

        print("\033[1;32m Current HANA version is: " +
              self._shared_parameters["hana_version"])
        print("\033[0m")

    def check_system_user_password(self):

        with open(os.devnull, 'w') as devnull:
            try:
                output = subprocess.check_output(
                    self._shared_parameters['sql_connection_string'] + ' "\\s"',
                    shell=True,
                    stderr=devnull)
                print(
                    '''\033[1;32m SYSTEM user's password has been validated successfully\n''')
                print("\033[0m")
            except:
                print(
                    "\033[1;31m Could not validate the SYSTEM user's password \n")
                print("\033[0m")

    def check_if_multinode(self):
        if self._shared_parameters["is_multi_node"]:
            print("\033[1;33m HANA is multi-node \n")
            print("\033[0m")
        else:
            print("\033[1;32m HANA is not multi-node \n")
            print("\033[0m")


class BackupSingleton(Borg):
    """This class now shares all its attributes among its various instances"""

    def __init__(self):
        Borg.__init__(self)

    @staticmethod
    def calculate_time_delta_data_backup(current_timestamp,
                                         last_data_backup_timestamp, time_delta):

        if last_data_backup_timestamp < (current_timestamp - time_delta):
            print("\033[1;33m The timestamp for the last data backup is too old: {}\n".format(
                last_data_backup_timestamp))
            print("\033[0m")
        else:
            print("\033[1;32m The timestamp for the last data backup is : {}\n".format(
                last_data_backup_timestamp))
            print("\033[0m")

    def check_data_backup_timestamp(self):

        date_time_now = datetime.now()
        time_delta_non_prod = timedelta(days=3)
        time_delta_prod = timedelta(days=1)
        command = self._shared_parameters['sql_connection_string'] + ''' \
            "select top 1 SYS_END_TIME from m_backup_catalog where \
            ENTRY_TYPE_NAME = 'complete data backup' order by SYS_END_TIME desc" \
                | awk 'BEGIN{FS="|"} {print $2}' | tail -n 1'''
        output = subprocess.check_output(
            command,
            shell=True).strip("\n").strip(" ")[:-3]
        last_data_backup_timestamp = (
            datetime.strptime(output, '%Y-%m-%d %H:%M:%S.%f'))
        usage = subprocess.check_output(
            self._shared_parameters['sql_connection_string'] +
            """ "select VALUE from sys.m_inifile_contents where FILE_NAME = 'global.ini' \
                and KEY = 'usage' and LAYER_NAME = 'DEFAULT'" \
                    | awk 'BEGIN{FS="|"} {print $2}' | tail -n 1""",
            shell=True).strip("\n").strip(" ")
        if usage == 'production':
            self.calculate_time_delta_data_backup(
                date_time_now, last_data_backup_timestamp, time_delta_prod)
        elif usage == 'test':
            self.calculate_time_delta_data_backup(
                date_time_now, last_data_backup_timestamp, time_delta_non_prod)
        elif usage == 'development':
            self.calculate_time_delta_data_backup(
                date_time_now, last_data_backup_timestamp, time_delta_non_prod)
        elif usage == 'custom':
            if self._shared_parameters["instance_number"] == '02':
                self.calculate_time_delta_data_backup(
                    date_time_now, last_data_backup_timestamp, time_delta_prod)
            else:
                self.calculate_time_delta_data_backup(
                    date_time_now, last_data_backup_timestamp, time_delta_non_prod)

    def check_backint(self):

        g = glob.glob(r'/usr/sbin/hdbbackint')

        if not g:
            print(
                "\033[1;31m Backint API for HANA is not installed on this host \n")
            print("\033[0m")
        else:
            module_string = '''strings /usr/sbin/hdbbackint | grep "@(#) Module Vers" \
            | awk -F " " '{print $NF}' '''
            module = subprocess.check_output(
                module_string, shell=True).replace(".", "")
            if module > BACKINT_MODULE:
                build_string = '''strings /usr/sbin/hdbbackint | grep "@(#) Build number" \
                | awk -F " " '{print $NF}' '''
                build = subprocess.check_output(
                    build_string, shell=True).replace(".", "")
                if build > BACKINT_BUILD:
                    print(
                        "\033[1;32m Backint API for HANA is installed and up to date \n")
                    print("\033[0m")
                else:
                    print(
                        "\033[1;31m Backint API for HANA is installed but it's not up to date \n")
                    print("Current Build Version is: {} \n".format(build))
                    print("Supported Module Version is {} and Build number si {} \n".format(
                        BACKINT_MODULE, BACKINT_BUILD))
                    print("\033[0m")
            else:
                print(
                    "\033[1;31m Backint API for HANA is installed but it's not up to date \n")
                print("Current Module Version is: {} \n".format(module))
                print("Supported Module Version is {} and Build number si {} \n".format(
                    BACKINT_MODULE, BACKINT_BUILD))
                print("\033[0m")

    def check_log_backup_using_backint(self):

        output = subprocess.check_output(
            """grep "log_backup_using_backint = false" /usr/sap/""" +
            self._shared_parameters["sid"] +
            """/SYS/global/hdb/custom/config/global.ini | wc -l""",
            shell=True)
        if output == 1:
            print("\033[1;33m Parameter global.ini -> [persistence] -> \
                    log_backup_using_backint is not set properly \n")
            print("\033[0m")
        else:
            command = self._shared_parameters['sql_connection_string'] + ''' "select VALUE \
                from sys.m_inifile_contents where FILE_NAME = 'global.ini' \
                and KEY = 'log_backup_using_backint' and LAYER_NAME = 'DEFAULT'" \
                    | awk 'BEGIN{FS="|"} {print $2}' | tail -n 1'''
            output = subprocess.check_output(
                command,
                shell=True).strip("\n").strip(" ")
            if output == 'false':
                print("\033[1;32m Parameter global.ini -> [persistence] -> \
                        log_backup_using_backint is set properly \n")
                print("\033[0m")
            else:
                print("\033[1;33m Parameter global.ini -> [persistence] -> \
                        log_backup_using_backint is not set properly \n")
                print("\033[0m")

    def check_log_backup_basepath(self):

        output = subprocess.check_output(
            """ grep "basepath_logbackup" /usr/sap/""" +
            self._shared_parameters["sid"] +
            """/SYS/global/hdb/custom/config/global.ini | awk -F "=" '{print $NF}' """,
            shell=True).strip("\n").strip(" ")
        if output in ("/hana_backup/" + self._shared_parameters["sid"] + "/log",
                      "/hana/backup/" + self._shared_parameters["sid"] + "/log"):
            print(
                "\033[1;32m Parameter global.ini -> [persistence] -> \
                    basepath_logbackup is set properly \n")
            print("\033[0m")
        else:
            print(
                "\033[1;33m Parameter global.ini -> [persistence] -> \
                    basepath_logbackup is not set properly \n")
            print("\033[0m")


class SidSingleton(Borg):
    """This class now shares all its attributes among its various instances"""

    def __init__(self):
        Borg.__init__(self)

    @staticmethod
    def check_password():
        sid_password = getpass.getpass('Provide the <sid>adm user password: ')
        process = subprocess.Popen(
            ['sudo', '-kS'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        process.stdin.write(sid_password + '\n')
        process.communicate()
        if process.returncode:
            print('\033[0;31m \nLog in with <sid>adm user was not possible')
            print("\033[0m")
        else:
            print('\033[1;32m \nLog in with <sid>adm user was successful')
            print("\033[0m")

    def check_attributes(self):

        output = subprocess.check_output(
            'ldapsearch -x -LLL cn=' +
            self._shared_parameters['sid'] + ' | wc -l',
            shell=True).strip("\n").strip(" ")
        if output == 0:
            print("\033[1;32m User " + self._shared_parameters['sid'] +
                  ' is not registered in LDAP. LOCAL authentication will be used')
            print("\033[0m")
            self.check_password()
        else:
            print("\033[1;32m User " +
                  self._shared_parameters['sid'] + ' is registered in LDAP')
            print("\033[0m")
            output = subprocess.check_output(
                'grep ' +
                self._shared_parameters['sid'] + ' /etc/passwd | wc -l',
                shell=True).strip("\n").strip(" ")
            if output == 0:
                print("\033[1;32m User " + self._shared_parameters['sid'] +
                      ' does not exist as LOCAL. LDAP authentication will be used')
                print("\033[0m")
            else:
                ldapuid = subprocess.check_output(
                    'ldapsearch -x -LLL cn=' +
                    self._shared_parameters['sid'] +
                    ''' | grep uidNumber | awk -F ':' \'{print $NF'}''',
                    shell=True).strip("\n").strip(" ")
                ldapgid = subprocess.check_output(
                    'ldapsearch -x -LLL cn=' +
                    self._shared_parameters['sid'] +
                    ''' | grep gidNumber | awk -F ':' '{print $NF'}''',
                    shell=True).strip("\n").strip(" ")
                localuid = subprocess.check_output(
                    'grep ' +
                    self._shared_parameters['sid'] +
                    ''' /etc/passwd | awk -F ':' '{print $3}' ''',
                    shell=True).strip("\n").strip(" ")
                localgid = subprocess.check_output(
                    'grep ' +
                    self._shared_parameters['sid'] +
                    ''' /etc/passwd | awk -F ':' '{print $4}' ''',
                    shell=True).strip("\n").strip(" ")
                if localuid and ldapuid != localuid:
                    print("\033[1;33m User " + self._shared_parameters['sid'] +
                          'exists both as LOCAL and LDAP but user IDs do not match')
                    print("Password verification might not be reliable")
                    print("\033[0m")
                elif localuid and ldapuid == localuid:
                    print("\033[1;33m User " + self._shared_parameters['sid'] +
                          'exists both as LOCAL and LDAP and user IDs match')
                    print("Password verification might not be reliable")
                    print("\033[0m")

                if localgid and ldapgid != localgid:
                    print("\033[1;33m User " + self._shared_parameters['sid'] +
                          'exists both as LOCAL and LDAP but group IDs do not match')
                    print("Password verification might not be reliable")
                    print("\033[0m")
                elif localgid and ldapgid == localgid:
                    print("\033[1;33m User " + self._shared_parameters['sid'] +
                          'exists both as LOCAL and LDAP and group IDs match')
                    print("Password verification might not be reliable")
                    print("\033[0m")

            self.check_password()


class Facade:

    def __init__(self, system_password):
        self._parameter_manager = ParameterManagerSingleton(system_password)
        self._hana_checks = HanaChecksSingleton()
        self._backup_checks = BackupSingleton()
        self._sid_checks = SidSingleton()

    def trigger_hana_upgrade_checks(self):
        self._sid_checks.check_attributes()
        self._hana_checks.check_if_multinode()
        self._hana_checks.check_hana_services()
        self._hana_checks.check_hana_replication()
        self._hana_checks.check_hana_plugins()
        self._hana_checks.get_hana_version()
        self._hana_checks.check_system_user_password()
        self._backup_checks.check_backint()
        self._backup_checks.check_data_backup_timestamp()
        self._backup_checks.check_log_backup_using_backint()
        self._backup_checks.check_log_backup_basepath()


def main():
    logging.basicConfig(level=logging.DEBUG)

    if getpass.getuser() == 'root':
        sys.exit(
            "You must be authenticated with <sid>adm user in order to run the script \n")
    if len(sys.argv) == 2:
        facade = Facade(sys.argv[1])
        facade.trigger_hana_upgrade_checks()
    else:
        sys.exit(
            "You must pass only one parameter to the script, \
                which is the password for SYSTEM user \n")


if __name__ == '__main__':
    main()
