##############################################################################
# This script is intended to perform the pre-checks for HANA 1.0 upgrade
# Author: Catalin Mihai Popa -> I324220
# Used Facade structural pattern
# Used Singleton creational pattern
##############################################################################

import sys
import os
import getpass
import subprocess
import datetime
import re
import logging


class Borg:
	"""Borg class making class attributes global"""
	_shared_parameters = {}  # Parameter dictionary

	def __init__(self):
		self.__dict__ = self._shared_parameters  # Make it an attribute dictionary


class ParameterManagerSingleton(Borg):
	"""This class now shares all its attributes among its various instances"""

	def __init__(self, password):
		Borg.__init__(self)
		self._shared_parameters.update(system_pwd=password)
		self._shared_parameters.update(sid=os.getenv("SAPSYSTEMNAME"))
		self._shared_parameters.update(instance_number=os.getenv("DIR_INSTANCE")[-2:])

	def __str__(self):
		return str(self._shared_parameters)


class HanaChecksSingleton(Borg):
	"""This class now shares all its attributes among its various instances"""

	def __init__(self):
		Borg.__init__(self)
		self._shared_parameters.update(
			hana_version=subprocess.check_output("HDB version | grep version: | awk -F ' ' '{print $2}'", shell=True).replace("\n", ""))
		if re.findall(r'^2', self._shared_parameters['hana_version']):
			self._shared_parameters.update(hana_type='MDC')
		else:
			self._shared_parameters.update(hana_type='Non-MDC')
		if self._shared_parameters['hana_type'] is 'MDC':
			self._shared_parameters.update(
				sql_connection_string="hdbsql -i " + self._shared_parameters['instance_number'] + " -u SYSTEM -n localhost:3" + self._shared_parameters[
					'instance_number'] + "13 -p " + self._shared_parameters['system_pwd'])
		else:
			self._shared_parameters.update(
				sql_connection_string="hdbsql -i " + self._shared_parameters['instance_number'] + " -u SYSTEM -p " + self._shared_parameters[
					'system_pwd'])
		os.chdir(r"/hana/shared/" + self._shared_parameters['sid'] + r"/global/hdb/custom/config")
		master_list = subprocess.check_output("""awk '$1 == "master" {for(i=3; i<=NF; i++) print substr($i,1,12)}' nameserver.ini""", shell=True).split()
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
			hs = "sapcontrol -nr " + self._shared_parameters['instance_number'] + " -function GetSystemInstanceList | grep hdb | awk -F ',' '{print $7}'"
			hana_services_status = subprocess.check_output(hs, shell=True).replace(" ", "").split()
		else:
			hs = "sapcontrol -nr " + self._shared_parameters['instance_number'] + " -function GetProcessList | grep hdb | awk -F ',' '{print $3}'"
			hana_services_status = subprocess.check_output(hs, shell=True).replace(" ", "").split()
		for status in hana_services_status:
			check = False if status != "GREEN" else True

		if check:
			print("\033[1;32m All HANA services are in GREEN state \n")
			print("\033[0m")
		else:
			print("\033[1;31m Not all HANA services are in GREEN state \n")
			print("\033[0m")

	def check_hana_replication(self):
		possible_hana_replication_modes = {"none": False, "primary": True, "sync": True, "syncmem": True, "async": True}
		m = "hdbnsutil -sr_state | grep mode: | awk -F ' ' '{print $2}'"
		hana_replication_mode = subprocess.check_output(m, shell=True)
		check = possible_hana_replication_modes.get(hana_replication_mode, False)
		if check:
			print("\033[1;33m Database has replication enabled \n")
			print("\033[0m")
		else:
			print("\033[1;32m Database is not configured for replication \n")
			print("\033[0m")

	def check_hana_plugins(self):
		try:
			os.chdir(r"/usr/sap/" + os.getenv("SAPSYSTEMNAME") + r"/SYS/exe/hdb/plugins")
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
		print("\033[1;32m Current HANA version is: " + self._shared_parameters["hana_version"])
		print("\033[0m")

	def check_system_user_password(self):
		with open(os.devnull, 'w') as devnull:
			try:
				output = subprocess.check_output('hdbsql -AjxU BKPMON "\s"', shell=True, stderr=devnull)
				print(output)
				print("\033[0m")
			except:
				print("\033[1;31m Could not validate the SYSTEM user's password \n")
				print("\033[0m")
				sys.exit()


class Facade:

	def __init__(self, password):
		self._parameter_manager = ParameterManagerSingleton(password)
		self._hana_checks = HanaChecksSingleton()

	def trigger_hana_upgrade_checks(self):
		print(self._hana_checks)
		self._hana_checks.check_hana_services()
		self._hana_checks.check_hana_replication()
		self._hana_checks.check_hana_plugins()
		self._hana_checks.get_hana_version()
		self._hana_checks.check_system_user_password()


def main():
	logging.basicConfig(level=logging.DEBUG)

	if getpass.getuser() == 'root':
		sys.exit("You must be authenticated with <sid>adm user in order to run the script \n")
	if len(sys.argv) == 2:
		facade = Facade(sys.argv[1])
		facade.trigger_hana_upgrade_checks()
	else:
		sys.exit("You must pass only one parameter to the script, which is the password for SYSTEM user \n")


if __name__ == '__main__':
	main()
