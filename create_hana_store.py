############################################################################
# This script is intended to create the keys in HDBuserstore of HANA
# It work with HANA Non-MDC and HANA MDC
# Author: Catalin Mihai Popa -> I324220
############################################################################

import os
import re
import subprocess
import sys
from datetime import datetime
from string import Template


class Borg:
    """Borg pattern making the class attributes global"""
    _shared_parameters = {}  # Attribute dictionary

    def __init__(self):
        # Make it an attribute dictionary
        self.__dict__ = self._shared_parameters


class CommonParameters(Borg):  # Inherits from the Borg class
    """This class now shares all its attributes among its various instances"""
    # This essentially makes the singleton objects an object-oriented global variable

    def __init__(self, argv):
        Borg.__init__(self)

        print(datetime.now().strftime(
            "\nTimestamp when the script was executed: %d/%m/%Y, %H:%M:%S\n\n\n"))

        os.chdir(r"/hana/shared/" +
                 self._shared_parameters['sid'] + r"/profile/")
        self._shared_parameters.update(password=argv)
        self._shared_parameters.update(sid=os.getenv("SAPSYSTEMNAME"))
        self._shared_parameters.update(
            instance_number=os.getenv("DIR_INSTANCE")[-2:])
        self._shared_parameters.update(
            localhostname=subprocess.check_output(
                'ls | egrep "(.*)_(.*)_(.*)"',
                shell=True).replace('\n', '')[-12:])
        self._shared_parameters.update(
            client_interface_name=self._shared_parameters['localhostname'][0:-2])

        output = subprocess.check_output(
            ['hdbnsutil -printSystemInformation'], shell=True).splitlines(1)
        for line in output:
            if "SingleDB" in line:
                self._shared_parameters['is_mdc'] = False
            elif "MultiDB" in line:
                self._shared_parameters['is_mdc'] = False

    def __str__(self):
        # Returns the attribute dictionary for printing
        return str(self._shared_parameters)


class HDBUserStoreClass(object):

    def __init__(self, password):

        hana_type = subprocess.check_output(
            ['hdbnsutil -printSystemInformation'], shell=True).splitlines(1)

        for line in hana_type:
            if "SingleDB" in line:
                self.is_mdc = False
                date_execution = datetime.now()
                print(date_execution.strftime(
                    "\nDate and time when the script was executed: %x, %H:%M"))
                print("\n\n\n")
                print(
                    re.sub(r"\s+", " ",
                           """################################# \t Print HANA Type\t
                            # """))
                print("\t\t\t\t HANA is Non-MDC")
                print(
                    re.sub(r"\s+", "",
                           """####################################
                           # """)
                )
                print("\n\n\n")
            elif "MultiDB" in line:
                self.is_mdc = True
                date_execution = datetime.now()
                print(date_execution.strftime(
                    "\nDate and time when the script was executed: %x, %H:%M"))
                print("\n\n\n")
                print(
                    re.sub(r"\s+", " ",
                           """################################# \t Print HANA Type\t
                            # """)
                )
                print("\t\t\t\t HANA is MDC")
                print(
                    re.sub(r"\s+", "",
                           """#########################################
                           # """)
                )
                print("\n\n\n")

        sap_system_name = subprocess.check_output(
            'echo $SAPSYSTEMNAME', shell=True).replace('\n', '')
        os.chdir(r"/hana/shared/" + sap_system_name + r"/profile/")
        profile_name = subprocess.check_output(
            'ls | egrep "(.*)_(.*)_(.*)"', shell=True).replace('\n', '')
        instance_number = subprocess.check_output(
            "less " +
            profile_name +
            ' | grep -w "SAPSYSTEM" ' +
            "| grep -o '..$'", shell=True).replace('\n', '')

        if not self.is_mdc:
            self.dparameters = {
                'sid': subprocess.check_output(
                    'echo $SAPSYSTEMNAME',
                    shell=True).replace('\n', ''),
                'sqlport': '3{}15'.format(instance_number),
                'localhostname': profile_name[-12:],
                'instance_number': instance_number,
                'passwordkey': password}
        else:
            self.dparameters = {
                'systemdbsid': subprocess.check_output(
                    'echo $SAPSYSTEMNAME',
                    shell=True).replace('\n', ''),
                'systemdbsqlport': subprocess.check_output(
                    """hdbnsutil -printSystemInformation |
					awk -v c=4 '/SYSTEMDB/{print $c}' |
					grep ""--only-matching '.....$' """,
                    shell=True).replace('\n', ''),
                'localhostname': profile_name[-12:],
                'client_interface_name': profile_name[-12:],
                'instance_number': instance_number,
                'passwordkey': password}

            os.chdir(r"/hana/shared/{0}/HDB{1}/{2}".format(
                sap_system_name,
                instance_number,
                self.dparameters['localhostname']))
            found = False
            daemon_file = 'daemon.ini'
            with open(daemon_file) as f:
                for line in f:
                    if not found and "[indexserver." in line:
                        self.dparameters['tenantsid'] = line.strip(
                            "[indexserver.").strip("\n").strip("]")
                        found = True

            self.dparameters['tenantsqlport'] = subprocess.check_output(
                "hdbnsutil -printSystemInformation | awk -v c=2 '/{0}/{{print $c}}' | grep "
                "--only-matching '.....$'".format(
                    self.dparameters['tenantsid']),
                shell=True).replace('\n', '')

        os.chdir(
            r"/hana/shared/" + sap_system_name +
            r"/global/hdb/custom/config")
        masters_list = subprocess.check_output(
            """awk '$1 == "master" {for(i=3; i<=NF; i++)
			 print substr($i,1,12)}' nameserver.ini""",
            shell=True).split()
        for i, v in enumerate(masters_list, start=1):
            self.dparameters["master_" + str(i)] = v
        # for i in range(len(masters_list)):
        # 	self.dparameters["master_" + str(i+1)] = masters_list[i]

        print(
            re.sub(r"\s+", " ",
                   """################################# \t Parameters to be
                    used in HDBuserstore keys creation
                    \t #################################""")
        )
        for k, v in self.dparameters.items():
            print('Parameter name: {} -> {}'.format(k, v))
        print(
            re.sub(r"\s+", "",
                   """######################################################
                   ################################################
                   # """)
        )
        print("\n\n\n")

        if 'master_2' in self.dparameters:
            self.is_multi_node = True
        else:
            self.is_multi_node = False

        replication_process = subprocess.Popen(
            ['hdbnsutil', '-sr_state'],
            stdout=subprocess.PIPE)
        out = replication_process.communicate()
        self.has_replication = True if "active primary site" in out else False

        if self.is_mdc:
            self.create_hdb_user_store_hana_mdc()
        else:
            self.create_hdb_user_store_hana_non_mdc()

    def create_hdb_user_store_hana_mdc(self):

        # W KEYS ########################
        w_key_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore set W
                    localhost:${systemdbsqlport}
                    SYSTEM ${passwordkey};""")
        )
        w_key_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET W
                    ${client_interface_name}:${systemdbsqlport}
                    SYSTEM ${passwordkey};""")
        )
        w_key_multi_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET W
                    "${master_1}:3${instance_number}13,
                    ${master_2}:3${instance_number}13,
                    ${master_3}:3${instance_number}13"
                    SYSTEM ${passwordkey};""")
        )
        w_key_tenant_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore set W${tenantsid}
                    localhost:${systemdbsqlport}@${tenantsid}
                    SYSTEM ${passwordkey};""")
        )
        w_key_tenant_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore set W${tenantsid}
                    ${client_interface_name}:${systemdbsqlport}@${tenantsid}
                    SYSTEM ${passwordkey};""")
        )
        w_key_tenant_multi_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore set W${tenantsid}
                    "${master_1}:3${instance_number}13@${tenant_sid},
                    ${master_2}:3${instance_number}13@${tenant_sid},
                    ${master_3}:3${instance_number}13@${tenant_sid}"
                    SYSTEM ''${passwordkey};""")
        )

        # SAPDBCTRL KEYS ########################
        sap_db_ctrl_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${systemdbsid}SAPDBCTRL
                    localhost:${systemdbsqlport}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${systemdbsid}SAPDBCTRL
                    ${client_interface_name}:${systemdbsqlport}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_tenant_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${systemdbsid}SAPDBCTRL${tenantsid}
                    localhost:${systemdbsqlport}@${tenantsid}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_tenant_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${systemdbsid}SAPDBCTRL${tenantsid}
                    ${client_interface_name}:${systemdbsqlport}@${tenantsid}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_tenant_port_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${systemdbsid}SAPDBCTRL${tenantsid}
                    localhost:${tenantsqlport}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_tenant_port_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${systemdbsid}SAPDBCTRL${tenantsid}
                    ${client_interface_name}:${tenantsqlport}
                    SAP_DBCTRL ${passwordkey};""")
        )

        # BKPMON KEYS ########################
        bkpmon_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET BKPMON
                    localhost:${systemdbsqlport}
                    BKPMON ${passwordkey};""")
        )
        bkpmon_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET BKPMON
                    ${client_interface_name}:${systemdbsqlport}
                    BKPMON ${passwordkey};""")
        )

        # BLADELOGIC KEYS ########################
        blade_logic_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET BLADELOGIC
                    localhost:${systemdbsqlport}
                    BLADELOGIC ${passwordkey};""")
        )
        blade_logic_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET BLADELOGIC
                    ${client_interface_name}:${systemdbsqlport}
                    BLADELOGIC ${passwordkey};""")
        )
        blade_logic_tenant_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET BLADELOGIC${tenantsid}
                    localhost:${systemdbsqlport}@${tenantsid}
                    BLADELOGIC ${passwordkey};""")
        )
        blade_logic_tenant_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET BLADELOGIC${tenantsid}
                    ${client_interface_name}:${systemdbsqlport}@${tenantsid}
                    BLADELOGIC ${passwordkey};""")
        )

        # CAM KEYS ########################
        cam_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET CAM
                    localhost:${systemdbsqlport}
                    CAM_CHANGE ${passwordkey};""")
        )
        cam_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET CAM
                    ${client_interface_name}:${systemdbsqlport}
                    CAM_CHANGE ${passwordkey};""")
        )
        cam_tenant_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET CAM${tenantsid}
                    localhost:${systemdbsqlport}@${tenantsid}
                    CAM_CHANGE ${passwordkey};""")
        )
        cam_tenant_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET CAM${tenantsid}
                    ${client_interface_name}:${systemdbsqlport}@${tenantsid}
                    CAM_CHANGE ''${passwordkey};""")
        )

        # NAGIOS KEYS ########################
        nagios_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET NAGIOS
                    localhost:${systemdbsqlport}
                    NAGIOS ${passwordkey};""")
        )
        nagios_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET NAGIOS
                    ${client_interface_name}:${systemdbsqlport}
                    NAGIOS ${passwordkey};""")
        )
        nagios_tenant_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET NAGIOS${tenantsid}
                    localhost:${systemdbsqlport}@{tenantsid}
                    NAGIOS ${passwordkey};""")
        )
        nagios_tenant_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET NAGIOS${tenantsid}
                    ${client_interface_name}:${systemdbsqlport}@${tenantsid}
                    NAGIOS ${passwordkey};""")
        )

        # STDMUSER KEYS ########################
        stdmuser_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET STDMUSER
                    localhost:${systemdbsqlport}
                    STDMUSER ${passwordkey};""")
        )
        stdmuser_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET STDMUSER
                    ${client_interface_name}:${systemdbsqlport}
                    STDMUSER ${passwordkey};""")
        )
        stdmuser_tenant_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET STDMUSER${tenantsid}
                    localhost:${systemdbsqlport}@${tenantsid}
                    STDMUSER ${passwordkey};""")
        )
        stdmuser_tenant_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET STDMUSER@${tenantsid}
                    ${client_interface_name}:${systemdbsqlport}@${tenantsid}
                    STDMUSER ${passwordkey};""")
        )

        print("\n\n\nTEST 1\n\n\n")

        # HANA MDC Multi Node with HA ########################
        if self.has_replication & self.is_multi_node:
            w_key = w_key_multi_templ.substitute(self.dparameters)
            w_tenant_key = w_key_tenant_multi_templ.substitute(
                self.dparameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(self.dparameters)
            sap_db_ctrl_tenant_key = sap_db_ctrl_tenant_templ.substitute(
                self.dparameters)
            sap_db_ctrl_tenant_port_key = sap_db_ctrl_tenant_port_templ.substitute(
                self.dparameters)
            bkpmon_key = bkpmon_templ.substitute(self.dparameters)
            blade_logic_key = blade_logic_templ.substitute(self.dparameters)
            blade_logic_tenant_key = blade_logic_tenant_templ.substitute(
                self.dparameters)
            cam_key = cam_templ.substitute(self.dparameters)
            cam_tenant_key = cam_tenant_templ.substitute(self.dparameters)
            nagios_key = nagios_templ.substitute(self.dparameters)
            nagios_tenant_key = nagios_tenant_templ.substitute(
                self.dparameters)
            stdmuser_key = stdmuser_templ.substitute(self.dparameters)
            stdmuser_tenant_key = stdmuser_tenant_templ.substitute(
                self.dparameters)

        # HANA MDC Single Node without HA ########################
        elif self.has_replication is not True & self.is_multi_node is not True:
            w_key = w_key_templ.substitute(self.dparameters)
            w_tenant_key = w_key_tenant_templ.substitute(
                self.dparameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(
                self.dparameters)
            sap_db_ctrl_tenant_key = sap_db_ctrl_tenant_templ.substitute(
                self.dparameters)
            sap_db_ctrl_tenant_port_key = sap_db_ctrl_tenant_port_templ.substitute(
                self.dparameters)
            bkpmon_key = bkpmon_templ.substitute(self.dparameters)
            blade_logic_key = blade_logic_templ.substitute(
                self.dparameters)
            blade_logic_tenant_key = blade_logic_tenant_templ.substitute(
                self.dparameters)
            cam_key = cam_templ.substitute(self.dparameters)
            cam_tenant_key = cam_tenant_templ.substitute(
                self.dparameters)
            nagios_key = nagios_templ.substitute(self.dparameters)
            nagios_tenant_key = nagios_tenant_templ.substitute(
                self.dparameters)
            stdmuser_key = stdmuser_templ.substitute(self.dparameters)
            stdmuser_tenant_key = stdmuser_tenant_templ.substitute(
                self.dparameters)

        # HANA MDC Multi Node without HA ########################
        elif self.has_replication is not True & self.is_multi_node is True:
            w_key = w_key_multi_templ.substitute(self.dparameters)
            w_tenant_key = w_key_tenant_multi_templ.substitute(
                self.dparameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(self.dparameters)
            sap_db_ctrl_tenant_key = sap_db_ctrl_tenant_templ.substitute(
                self.dparameters)
            sap_db_ctrl_tenant_port_key = sap_db_ctrl_tenant_port_templ.substitute(
                self.dparameters)
            bkpmon_key = bkpmon_templ.substitute(self.dparameters)
            blade_logic_key = blade_logic_templ.substitute(self.dparameters)
            blade_logic_tenant_key = blade_logic_tenant_templ.substitute(
                self.dparameters)
            cam_key = cam_templ.substitute(self.dparameters)
            cam_tenant_key = cam_tenant_templ.substitute(self.dparameters)
            nagios_key = nagios_templ.substitute(self.dparameters)
            nagios_tenant_key = nagios_tenant_templ.substitute(
                self.dparameters)
            stdmuser_key = stdmuser_templ.substitute(self.dparameters)
            stdmuser_tenant_key = stdmuser_tenant_templ.substitute(
                self.dparameters)

        elif self.has_replication is True & self.is_multi_node is not True:
            print("\n\n\nTEST 2\n\n\n")
            w_key = w_key_client_templ.substitute(self.dparameters)
            w_tenant_key = w_key_tenant_client_templ.substitute(
                self.dparameters)
            sap_db_ctrl_key = sap_db_ctrl_client_templ.substitute(
                self.dparameters)
            sap_db_ctrl_tenant_key = sap_db_ctrl_tenant_client_templ.substitute(
                self.dparameters)
            sap_db_ctrl_tenant_port_key = sap_db_ctrl_tenant_port_client_templ.substitute(
                self.dparameters)
            bkpmon_key = bkpmon_client_templ.substitute(self.dparameters)
            blade_logic_key = blade_logic_client_templ.substitute(
                self.dparameters)
            blade_logic_tenant_key = blade_logic_tenant_client_templ.substitute(
                self.dparameters)
            cam_key = cam_client_templ.substitute(self.dparameters)
            cam_tenant_key = cam_tenant_client_templ.substitute(
                self.dparameters)
            nagios_key = nagios_client_templ.substitute(self.dparameters)
            nagios_tenant_key = nagios_tenant_client_templ.substitute(
                self.dparameters)
            stdmuser_key = stdmuser_client_templ.substitute(self.dparameters)
            stdmuser_tenant_key = stdmuser_tenant_client_templ.substitute(
                self.dparameters)

        hdbuserstore_commands = {
            w_key, w_tenant_key, sap_db_ctrl_key, sap_db_ctrl_tenant_key,
            sap_db_ctrl_tenant_port_key, bkpmon_key, blade_logic_key,
            blade_logic_tenant_key, cam_key, cam_tenant_key, nagios_key,
            nagios_tenant_key, stdmuser_key, stdmuser_tenant_key}
        for cmd in hdbuserstore_commands:
            print("\n\n\nTEST\n\n\n")
            subprocess.call(cmd, shell=True)
        subprocess.call(['hdbuserstore list'], shell=True)

    def create_hdb_user_store_hana_non_mdc(self):

        # W KEYS ########################
        w_key_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore set W
                    localhost:${systemdbsqlport}
                    SYSTEM ${passwordkey};""")
        )
        w_key_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET W
                    ${client_interface_name}:${systemdbsqlport}
                    SYSTEM ${passwordkey};""")
        )
        w_key_multi_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET W
                    "${master_1}:3${instance_number}13,
                    ${master_2}:3${instance_number}13,
                    ${master_3}:3${instance_number}13"
                    SYSTEM ${passwordkey};""")
        )

        # SAPDBCTRL KEYS ########################
        sap_db_ctrl_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${systemdbsid}SAPDBCTRL
                    localhost:${systemdbsqlport}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${systemdbsid}SAPDBCTRL
                    ${client_interface_name}:${systemdbsqlport}
                    SAP_DBCTRL ${passwordkey};""")
        )

        # BKPMON KEYS ########################
        bkpmon_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET BKPMON
                    localhost:${systemdbsqlport}
                    BKPMON ${passwordkey};""")
        )
        bkpmon_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET BKPMON
                    ${client_interface_name}:${systemdbsqlport}
                    BKPMON ${passwordkey};""")
        )

        # BLADELOGIC KEYS ########################
        blade_logic_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET BLADELOGIC
                    localhost:${systemdbsqlport}
                    BLADELOGIC ${passwordkey};""")
        )
        blade_logic_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET BLADELOGIC
                    ${client_interface_name}:${systemdbsqlport}
                    BLADELOGIC ${passwordkey};""")
        )

        # CAM KEYS ########################
        cam_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET CAM
                    localhost:${systemdbsqlport}
                    CAM_CHANGE ${passwordkey};""")
        )
        cam_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET CAM
                    ${client_interface_name}:${systemdbsqlport}
                    CAM_CHANGE ${passwordkey};""")
        )

        # NAGIOS KEYS ########################
        nagios_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET NAGIOS
                    localhost:${systemdbsqlport}
                    NAGIOS ${passwordkey};""")
        )
        nagios_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET NAGIOS
                    ${client_interface_name}:${systemdbsqlport}
                    NAGIOS ${passwordkey};""")
        )

        # STDMUSER KEYS ########################
        stdmuser_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET STDMUSER
                    localhost:${systemdbsqlport}
                    STDMUSER ${passwordkey};""")
        )
        stdmuser_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET STDMUSER
                    ${client_interface_name}:${systemdbsqlport}
                    STDMUSER ${passwordkey};""")
        )

        # HANA Non-MDC Multi Node with HA ########################
        if self.has_replication & self.is_multi_node:
            w_key = w_key_multi_templ.substitute(self.dparameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(self.dparameters)
            bkpmon_key = bkpmon_templ.substitute(self.dparameters)
            blade_logic_key = blade_logic_templ.substitute(self.dparameters)
            cam_key = cam_templ.substitute(self.dparameters)
            nagios_key = nagios_templ.substitute(self.dparameters)
            stdmuser_key = stdmuser_templ.substitute(self.dparameters)

        # HANA Non-MDC Single Node with HA ########################
        elif self.has_replication is True & self.is_multi_node is not True:
            w_key = w_key_client_templ.substitute(self.dparameters)
            sap_db_ctrl_key = sap_db_ctrl_client_templ.substitute(
                self.dparameters)
            bkpmon_key = bkpmon_client_templ.substitute(self.dparameters)
            blade_logic_key = blade_logic_client_templ.substitute(
                self.dparameters)
            cam_key = cam_client_templ.substitute(self.dparameters)
            nagios_key = nagios_client_templ.substitute(self.dparameters)
            stdmuser_key = stdmuser_client_templ.substitute(self.dparameters)

        # HANA Non-MDC Multi Node without HA ########################
        elif self.has_replication is not True & self.is_multi_node is True:
            w_key = w_key_multi_templ.substitute(self.dparameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(self.dparameters)
            bkpmon_key = bkpmon_templ.substitute(self.dparameters)
            blade_logic_key = blade_logic_templ.substitute(self.dparameters)
            cam_key = cam_templ.substitute(self.dparameters)
            nagios_key = nagios_templ.substitute(self.dparameters)
            stdmuser_key = stdmuser_templ.substitute(self.dparameters)

        # HANA Non-MDC Single Node without HA ########################
        elif self.has_replication is not True & self.is_multi_node is not True:
            w_key = w_key_templ.substitute(self.dparameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(self.dparameters)
            bkpmon_key = bkpmon_templ.substitute(self.dparameters)
            blade_logic_key = blade_logic_templ.substitute(self.dparameters)
            cam_key = cam_templ.substitute(self.dparameters)
            nagios_key = nagios_templ.substitute(self.dparameters)
            stdmuser_key = stdmuser_templ.substitute(self.dparameters)

        hdbuserstore_commands = {w_key, sap_db_ctrl_key, bkpmon_key,
                                 blade_logic_key, cam_key, nagios_key, stdmuser_key}
        for cmd in hdbuserstore_commands:
            subprocess.call(cmd, shell=True)
        subprocess.call(['hdbuserstore list'], shell=True)


def main():
    if os.getlogin() == 'root':
        sys.exit(
            re.sub(r"\s+", "",
                   """You must be authenticated with <sid>adm
                    user in order to run the script""")
        )
    if len(sys.argv) == 2:
        CommonParameters(sys.argv[1])
    else:
        sys.exit(
            re.sub(r"\s+", "",
                   """You must pass only one parameter to the script,
                    which is the password for the HDBuserstore keys""")
        )


if __name__ == '__main__':
    main()