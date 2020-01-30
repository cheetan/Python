############################################################################
# This script is intended to create the keys in HDBuserstore of HANA
# It work with HANA Non-MDC and HANA MDC
# Author: Catalin Mihai Popa -> I324220
# Used Facade structural pattern
# Used Singleton creational pattern
############################################################################

import getpass
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


class CommonParametersSingleton(Borg):  # Inherits from the Borg class
    """This class now shares all its attributes among its various instances"""
    # This essentially makes the singleton objects an object-oriented global variable

    def __init__(self, argv):
        Borg.__init__(self)

        print(datetime.now().strftime(
            "\nTimestamp when the script was executed: %d/%m/%Y, %H:%M:%S\n\n\n"))

        self._shared_parameters.update(sid=os.getenv("SAPSYSTEMNAME"))
        os.chdir(r"/hana/shared/" +
                 self._shared_parameters['sid'] + r"/profile/")
        self._shared_parameters.update(passwordkey=argv)
        self._shared_parameters.update(
            instance_number=os.getenv("DIR_INSTANCE")[-2:])
        self._shared_parameters.update(
            localhostname=subprocess.check_output(
                'ls | egrep "(.*)_(.*)_(.*)"',
                shell=True).replace('\n', '')[-12:])
        self._shared_parameters.update(
            client_interface_name=self._shared_parameters['localhostname'][0:-2])

        os.chdir(
            r"/hana/shared/" +
            self._shared_parameters['sid'] +
            r"/global/hdb/custom/config")
        masters_list = subprocess.check_output(
            """awk '$1 == "master" {for(i=3; i<=NF; i++)
			 print substr($i,1,12)}' nameserver.ini""",
            shell=True).split()
        for i, value in enumerate(masters_list, start=1):
            self._shared_parameters["master_" + str(i)] = value
        if 'master_2' in self._shared_parameters:
            self._shared_parameters.update(is_multi_node=True)
        else:
            self._shared_parameters.update(is_multi_node=False)

        hdbnsutil_output = subprocess.Popen(
            ['hdbnsutil', '-sr_state'],
            stdout=subprocess.PIPE).communicate()
        if "active primary site" in hdbnsutil_output:
            self._shared_parameters.update(has_replication=True)
        else:
            self._shared_parameters.update(has_replication=False)

    def __str__(self):
        # Returns the attribute dictionary for printing
        return str(self._shared_parameters)


class HanaParametersBasedTypeSingleton(Borg):  # Inherits from the Borg class
    """This class now shares all its attributes among its various instances"""
    # This essentially makes the singleton objects an object-oriented global variable

    def __init__(self):
        Borg.__init__(self)

        output = subprocess.check_output(
            ['hdbnsutil -printSystemInformation'], shell=True).splitlines(1)
        for line in output:
            if "SingleDB" in line:
                self._shared_parameters.update(is_mdc=False)
            elif "MultiDB" in line:
                self._shared_parameters.update(is_mdc=True)

        if self._shared_parameters['is_mdc'] is True:
            output = subprocess.check_output(
                """hdbnsutil -printSystemInformation |
					 awk -v c=4 '/SYSTEMDB/{print $c}' |
					 grep ""--only-matching '.....$' """,
                shell=True).replace('\n', '')
            self._shared_parameters.update(systemdbsqlport=output)

            os.chdir(r"/hana/shared/{0}/HDB{1}/{2}".format(
                self._shared_parameters['sid'],
                self._shared_parameters['instance_number'],
                self._shared_parameters['localhostname']))
            found = False
            daemon_file = 'daemon.ini'
            with open(daemon_file) as file:
                for line in file:
                    if not found and "[indexserver." in line:
                        self._shared_parameters['tenantsid'] = line.strip(
                            "[indexserver.").strip("\n").strip("]")
                        found = True
            self._shared_parameters['tenantsqlport'] = subprocess.check_output(
                """hdbnsutil -printSystemInformation |
                 awk -v c=2 '/{0}/{{print $c}}' |
                 grep --only-matching '.....$'""".format(self._shared_parameters['tenantsid']),
                shell=True).replace('\n', '')

            self.create_hana_hdb_user_store_mdc()
        else:
            self._shared_parameters.update(
                sqlport='3{}15'.format(
                    self._shared_parameters['instance_number'])
            )

            self.create_hana_hdb_user_store_non_mdc()

    def __str__(self):
        # Returns the attribute dictionary for printing
        return str(self._shared_parameters)

    def create_hana_hdb_user_store_mdc(self):
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
                   """hdbuserstore SET ${sid}SAPDBCTRL
                    localhost:${systemdbsqlport}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${sid}SAPDBCTRL
                    ${client_interface_name}:${systemdbsqlport}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_tenant_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${sid}SAPDBCTRL${tenantsid}
                    localhost:${systemdbsqlport}@${tenantsid}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_tenant_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${sid}SAPDBCTRL${tenantsid}
                    ${client_interface_name}:${systemdbsqlport}@${tenantsid}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_tenant_port_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${sid}SAPDBCTRL${tenantsid}
                    localhost:${tenantsqlport}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_tenant_port_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${sid}SAPDBCTRL${tenantsid}
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

        # HANA Multi Node with HA ########################
        if (self._shared_parameters['is_multi_node'] is True &
                self._shared_parameters['has_replication'] is True):
            w_key = w_key_multi_templ.substitute(self._shared_parameters)
            w_tenant_key = w_key_tenant_multi_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_tenant_key = sap_db_ctrl_tenant_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_tenant_port_key = sap_db_ctrl_tenant_port_templ.substitute(
                self._shared_parameters)
            bkpmon_key = bkpmon_templ.substitute(self._shared_parameters)
            blade_logic_key = blade_logic_templ.substitute(
                self._shared_parameters)
            blade_logic_tenant_key = blade_logic_tenant_templ.substitute(
                self._shared_parameters)
            cam_key = cam_templ.substitute(self._shared_parameters)
            cam_tenant_key = cam_tenant_templ.substitute(
                self._shared_parameters)
            nagios_key = nagios_templ.substitute(self._shared_parameters)
            nagios_tenant_key = nagios_tenant_templ.substitute(
                self._shared_parameters)
            stdmuser_key = stdmuser_templ.substitute(self._shared_parameters)
            stdmuser_tenant_key = stdmuser_tenant_templ.substitute(
                self._shared_parameters)

        # HANA Single Node without HA ########################
        elif(self._shared_parameters['has_replication'] is False &
             self._shared_parameters['is_multi_node'] is False):
            w_key = w_key_templ.substitute(self._shared_parameters)
            w_tenant_key = w_key_tenant_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_tenant_key = sap_db_ctrl_tenant_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_tenant_port_key = sap_db_ctrl_tenant_port_templ.substitute(
                self._shared_parameters)
            bkpmon_key = bkpmon_templ.substitute(self._shared_parameters)
            blade_logic_key = blade_logic_templ.substitute(
                self._shared_parameters)
            blade_logic_tenant_key = blade_logic_tenant_templ.substitute(
                self._shared_parameters)
            cam_key = cam_templ.substitute(self._shared_parameters)
            cam_tenant_key = cam_tenant_templ.substitute(
                self._shared_parameters)
            nagios_key = nagios_templ.substitute(self._shared_parameters)
            nagios_tenant_key = nagios_tenant_templ.substitute(
                self._shared_parameters)
            stdmuser_key = stdmuser_templ.substitute(self._shared_parameters)
            stdmuser_tenant_key = stdmuser_tenant_templ.substitute(
                self._shared_parameters)

        # HANA Multi Node without HA ########################
        elif(self._shared_parameters['has_replication'] is False &
             self._shared_parameters['is_multi_node'] is True):
            w_key = w_key_multi_templ.substitute(self._shared_parameters)
            w_tenant_key = w_key_tenant_multi_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_tenant_key = sap_db_ctrl_tenant_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_tenant_port_key = sap_db_ctrl_tenant_port_templ.substitute(
                self._shared_parameters)
            bkpmon_key = bkpmon_templ.substitute(self._shared_parameters)
            blade_logic_key = blade_logic_templ.substitute(
                self._shared_parameters)
            blade_logic_tenant_key = blade_logic_tenant_templ.substitute(
                self._shared_parameters)
            cam_key = cam_templ.substitute(self._shared_parameters)
            cam_tenant_key = cam_tenant_templ.substitute(
                self._shared_parameters)
            nagios_key = nagios_templ.substitute(self._shared_parameters)
            nagios_tenant_key = nagios_tenant_templ.substitute(
                self._shared_parameters)
            stdmuser_key = stdmuser_templ.substitute(self._shared_parameters)
            stdmuser_tenant_key = stdmuser_tenant_templ.substitute(
                self._shared_parameters)

        # HANA Single Node with HA ########################
        elif(self._shared_parameters['has_replication'] is True &
             self._shared_parameters['is_multi_node'] is False):
            w_key = w_key_client_templ.substitute(self._shared_parameters)
            w_tenant_key = w_key_tenant_client_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_key = sap_db_ctrl_client_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_tenant_key = sap_db_ctrl_tenant_client_templ.substitute(
                self._shared_parameters)
            sap_db_ctrl_tenant_port_key = sap_db_ctrl_tenant_port_client_templ.substitute(
                self._shared_parameters)
            bkpmon_key = bkpmon_client_templ.substitute(
                self._shared_parameters)
            blade_logic_key = blade_logic_client_templ.substitute(
                self._shared_parameters)
            blade_logic_tenant_key = blade_logic_tenant_client_templ.substitute(
                self._shared_parameters)
            cam_key = cam_client_templ.substitute(self._shared_parameters)
            cam_tenant_key = cam_tenant_client_templ.substitute(
                self._shared_parameters)
            nagios_key = nagios_client_templ.substitute(
                self._shared_parameters)
            nagios_tenant_key = nagios_tenant_client_templ.substitute(
                self._shared_parameters)
            stdmuser_key = stdmuser_client_templ.substitute(
                self._shared_parameters)
            stdmuser_tenant_key = stdmuser_tenant_client_templ.substitute(
                self._shared_parameters)

        hdbuserstore_commands = {
            w_key, w_tenant_key, sap_db_ctrl_key, sap_db_ctrl_tenant_key,
            sap_db_ctrl_tenant_port_key, bkpmon_key, blade_logic_key,
            blade_logic_tenant_key, cam_key, cam_tenant_key, nagios_key,
            nagios_tenant_key, stdmuser_key, stdmuser_tenant_key}
        for cmd in hdbuserstore_commands:
            subprocess.call(cmd, shell=True)
        subprocess.call(['hdbuserstore list'], shell=True)

    def create_hana_hdb_user_store_non_mdc(self):
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
                   """hdbuserstore SET ${sid}SAPDBCTRL
                    localhost:${systemdbsqlport}
                    SAP_DBCTRL ${passwordkey};""")
        )
        sap_db_ctrl_client_templ = Template(
            re.sub(r"\s+", " ",
                   """hdbuserstore SET ${sid}SAPDBCTRL
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

        # HANA Multi Node with HA ########################
        if(self._shared_parameters['has_replication'] is True &
           self._shared_parameters['is_multi_node'] is True):
            w_key = w_key_multi_templ.substitute(self._shared_parameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(
                self._shared_parameters)
            bkpmon_key = bkpmon_templ.substitute(self._shared_parameters)
            blade_logic_key = blade_logic_templ.substitute(
                self._shared_parameters)
            cam_key = cam_templ.substitute(self._shared_parameters)
            nagios_key = nagios_templ.substitute(self._shared_parameters)
            stdmuser_key = stdmuser_templ.substitute(self._shared_parameters)

        # HANA Single Node with HA ########################
        elif(self._shared_parameters['has_replication'] is True &
             self._shared_parameters['is_multi_node'] is False):
            w_key = w_key_client_templ.substitute(self._shared_parameters)
            sap_db_ctrl_key = sap_db_ctrl_client_templ.substitute(
                self._shared_parameters)
            bkpmon_key = bkpmon_client_templ.substitute(
                self._shared_parameters)
            blade_logic_key = blade_logic_client_templ.substitute(
                self._shared_parameters)
            cam_key = cam_client_templ.substitute(self._shared_parameters)
            nagios_key = nagios_client_templ.substitute(
                self._shared_parameters)
            stdmuser_key = stdmuser_client_templ.substitute(
                self._shared_parameters)

        # HANA Multi Node without HA ########################
        elif(self._shared_parameters['has_replication'] is False &
             self._shared_parameters['is_multi_node'] is True):
            w_key = w_key_multi_templ.substitute(self._shared_parameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(
                self._shared_parameters)
            bkpmon_key = bkpmon_templ.substitute(self._shared_parameters)
            blade_logic_key = blade_logic_templ.substitute(
                self._shared_parameters)
            cam_key = cam_templ.substitute(self._shared_parameters)
            nagios_key = nagios_templ.substitute(self._shared_parameters)
            stdmuser_key = stdmuser_templ.substitute(self._shared_parameters)

        # HANA Single Node without HA ########################
        elif(self._shared_parameters['has_replication'] is False &
             self._shared_parameters['is_multi_node'] is False):
            w_key = w_key_templ.substitute(self._shared_parameters)
            sap_db_ctrl_key = sap_db_ctrl_templ.substitute(
                self._shared_parameters)
            bkpmon_key = bkpmon_templ.substitute(self._shared_parameters)
            blade_logic_key = blade_logic_templ.substitute(
                self._shared_parameters)
            cam_key = cam_templ.substitute(self._shared_parameters)
            nagios_key = nagios_templ.substitute(self._shared_parameters)
            stdmuser_key = stdmuser_templ.substitute(self._shared_parameters)

        hdbuserstore_commands = {w_key, sap_db_ctrl_key, bkpmon_key,
                                 blade_logic_key, cam_key, nagios_key, stdmuser_key}
        for cmd in hdbuserstore_commands:
            subprocess.call(cmd, shell=True)
        subprocess.call(['hdbuserstore list'], shell=True)


class Facade:

    def __init__(self, password):
        self._initialize_parameters = CommonParametersSingleton(password)
        self._hana_type = HanaParametersBasedTypeSingleton()

    def __str__(self):
        return str(self._initialize_parameters)


def main():
    if getpass.getuser() == 'root':
        sys.exit(
            "You must be authenticated with <sid>adm user in order to run the script \n")
    if len(sys.argv) == 2:
        facade = Facade(sys.argv[1])
        print(facade)
    else:
        sys.exit(
            "You must pass only one parameter to the script, \
                which is the password for the keys \n")


if __name__ == '__main__':
    main()
