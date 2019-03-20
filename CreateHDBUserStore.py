##############################################################################
# This script is intended to create the keys in HDBuserstore for HANA Non-MDC and HANA MDC
# Author: Catalin Mihai Popa -> i324220
##############################################################################

import sys
import os
import subprocess
import datetime
from datetime import datetime


class HDBUserStoreClass(object):

	def __init__(self, password):

		hana_type = subprocess.check_output(['hdbnsutil -printSystemInformation'], shell=True).splitlines(1)

		for line in hana_type:
			if "SingleDB" in line:
				self.is_mdc = False
				date_execution = datetime.now()
				print(date_execution.strftime("Date and time when the script was executed: %x, %H:%M"))
				print("\n\n\n")
				print("################################# \t Print HANA Type \t#################################")
				print("\t\t\t\t\t HANA is Non-MDC")
				print("#################################################################################################")
				print("\n\n\n")
			elif "MultiDB" in line:
				self.is_mdc = True
				date_execution = datetime.now()
				print(date_execution.strftime("Date and time when the script was executed: %x, %H:%M"))
				print("\n\n\n")
				print("################################# \t Print HANA Type \t#################################")
				print("\t\t\t\t\t HANA is MDC")
				print("#################################################################################################")
				print("\n\n\n")

		sap_system_name = subprocess.check_output('echo $SAPSYSTEMNAME', shell=True).replace('\n', '')
		os.chdir(r"/hana/shared/" + sap_system_name + r"/profile/")
		profile_name = subprocess.check_output('ls | egrep "(.*)_(.*)_(.*)"', shell=True).replace('\n', '')
		instance_number = subprocess.check_output("less " + profile_name + ' | grep -w "SAPSYSTEM" ' + "| grep -o '..$'", shell=True).replace('\n', '')

		if not self.is_mdc:
			self.dparameters = {'sid': subprocess.check_output('echo $SAPSYSTEMNAME', shell=True).replace('\n', ''),
								'sqlport': '3{}15'.format(instance_number),
								'localhostname': profile_name[-12:],
			                    'instance_number': instance_number,
			                    'passwordkey': password}
		else:
			self.dparameters = {'systemdbsid': subprocess.check_output('echo $SAPSYSTEMNAME', shell=True).replace('\n', ''),
								'systemdbsqlport': subprocess.check_output("hdbnsutil -printSystemInformation | awk -v c=4 '/SYSTEMDB/{print $c}' | grep --only-matching '.....$'", shell=True).replace('\n', ''),
								'localhostname': profile_name[-12:],
								# 'tenantsid': subprocess.check_output("hdbnsutil -printSystemInformation | awk -v c=1 'NR==4 {print $c}'", shell=True).replace('\n', ''),
								# 'tenantsqlport': subprocess.check_output("hdbnsutil -printSystemInformation | awk -v c=2 'NR==4 {print $c}' | grep --only-matching '.....$'", shell=True).replace('\n', ''),
								'instance_number': instance_number,
								'passwordkey': password}

			os.chdir(r"/hana/shared/{0}/HDB{1}/{2}".format(sap_system_name, instance_number, self.dparameters['localhostname']))
			found = False
			daemon_file = 'daemon.ini'
			with open(daemon_file) as f:
				for line in f:
					if not found and "[indexserver." in line:
						self.dparameters['tenantsid'] = line.strip("[indexserver.").strip("\n").strip("]")
						found = True

			self.dparameters['tenantsqlport'] = subprocess.check_output("hdbnsutil -printSystemInformation | awk -v c=2 '/{0}/{{print $c}}' | grep --only-matching '.....$'".format(self.dparameters['tenantsid']), shell=True).replace('\n', '')

		os.chdir(r"/hana/shared/" + sap_system_name + r"/global/hdb/custom/config")
		self.dparameters['master_hosts'] = subprocess.check_output("""awk '$1 == "master" {for(i=3; i<=NF; i++) print substr($i,1,12)}' nameserver.ini""", shell=True).split()


		print("################################# \t Parameters to be used in HDBuserstore keys creation \t#################################")
		for k, v in self.dparameters.iteritems():
			print('Parameter name: {} -> {}'.format(k, v))
		print("#################################################################################################################################")
		print("\n\n\n")

		if len(self.dparameters['master_hosts']) > 1:
			self.is_multi_node = True
		else:
			self.is_multi_node = False

		replication_process = subprocess.Popen(['hdbnsutil', '-sr_state'], stdout=subprocess.PIPE)
		out = replication_process.communicate()
		self.has_replication = True if "active primary site" in out else False

		if self.is_mdc:
			self.create_hdb_user_store_hana_mdc()
		else:
			self.create_hdb_user_store_hana_non_mdc()

	def create_hdb_user_store_hana_mdc(self):

		if self.has_replication & self.is_multi_node:
			wkey = 'hdbuserstore SET W "{0}:3{1}13, {2}:3{1}13, {3}:3{1}13" SYSTEM {4};'.format(self.dparameters.get('master_hosts')[0], self.dparameters.get('instance_number'), self.dparameters.get('master_hosts')[1],
			                                                                                           self.dparameters.get('master_hosts')[2], self.dparameters.get('passwordkey'))
			wtenantkey = 'hdbuserstore SET W{0} "{1}:3{2}13@{0}, {3}:3{2}13@{0}, {4}:3{2}13@{0}" SYSTEM {5};'.format(self.dparameters.get('tenantsid'), self.dparameters.get('master_hosts')[0], self.dparameters.get(
				'instance_number'), self.dparameters.get('master_hosts')[1], self.dparameters.get('master_hosts')[2], self.dparameters.get('passwordkey'))
			systemdbsapdbctrlkey = 'hdbuserstore SET {}SAPDBCTRL localhost:{} SAP_DBCTRL {}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			systemdbsapdbctrltenantkey = 'hdbuserstore SET {0}SAPDBCTRL{1} localhost:{2}@{1} SAP_DBCTRL {3}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'),
			                                                                                                        self.dparameters.get('passwordkey'))
			systemdbsapdbctrltenantportkey = 'hdbuserstore SET {0}SAPDBCTRL{1} localhost:{1} SAP_DBCTRL {2}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('tenantsqlport'), sys.argv())
			bkpmonkey = 'hdbuserstore SET BKPMON localhost:{} BKPMON {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			bladelogickey = 'hdbuserstore SET BLADELOGIC localhost:{} BLADELOGIC {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			bladelogictenantkey = 'hdbuserstore SET BLADELOGIC{0} localhost:{1}@{0} BLADELOGIC {2}'.format(self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			camkey = 'hdbuserstore SET CAM localhost:{} CAM_CHANGE {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			camtenantkey = 'hdbuserstore SET CAM{0} localhost:{1}@{0} CAM_CHANGE {2}'.format(self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))

			hdbuserstorecommands = {wkey, wtenantkey, systemdbsapdbctrlkey, systemdbsapdbctrltenantkey, systemdbsapdbctrltenantportkey, bkpmonkey, bladelogickey, bladelogictenantkey, camkey, camtenantkey}
			for cmd in hdbuserstorecommands:
				subprocess.call(cmd, shell=True)

			subprocess.call(['hdbuserstore list'], shell=True)

		elif self.has_replication is True & self.is_multi_node is not True:
			wkey = 'hdbuserstore SET W localhost:{} SYSTEM {};'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			wtenantkey = 'hdbuserstore SET W{} localhost:{}@{} SYSTEM {};'.format(self.dparameters.get('tenantsid'), self.dparameters.get('tenantsqlport'), self.dparameters.get('tenantsid'), self.dparameters.get('passwordkey'))
			systemdbsapdbctrlkey = 'hdbuserstore SET {}SAPDBCTRL localhost:{} SAP_DBCTRL {}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			systemdbsapdbctrltenantkey = 'hdbuserstore SET {0}SAPDBCTRL{1} localhost:{2}@{1} SAP_DBCTRL {3}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'),
			                                                                                                        self.dparameters.get('passwordkey'))
			systemdbsapdbctrltenantportkey = 'hdbuserstore SET {0}SAPDBCTRL{1} localhost:{1} SAP_DBCTRL {2}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('tenantsqlport'), self.dparameters.get('passwordkey'))
			bkpmonkey = 'hdbuserstore SET BKPMON localhost:{} BKPMON {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			bladelogickey = 'hdbuserstore SET BLADELOGIC localhost:{} BLADELOGIC {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			bladelogictenantkey = 'hdbuserstore SET BLADELOGIC{0} localhost:{1}@{0} BLADELOGIC {2}'.format(self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			camkey = 'hdbuserstore SET CAM localhost:{} CAM_CHANGE {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			camtenantkey = 'hdbuserstore SET CAM{0} localhost:{1}@{0} CAM_CHANGE {2}'.format(self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))

			hdbuserstorecommands = {wkey, wtenantkey, systemdbsapdbctrlkey, systemdbsapdbctrltenantkey, systemdbsapdbctrltenantportkey, bkpmonkey, bladelogickey, bladelogictenantkey, camkey, camtenantkey}
			for cmd in hdbuserstorecommands:
				subprocess.call(cmd, shell=True)

			subprocess.call(['hdbuserstore list'], shell=True)

		elif self.has_replication is not True & self.is_multi_node is True:
			wkey = 'hdbuserstore SET W "{0}:3{1}13, {2}:3{1}13, {3}:3{1}13" SYSTEM {4};'.format(self.dparameters.get('master_hosts')[0], self.dparameters.get('instance_number'), self.dparameters.get('master_hosts')[1],
			                                                                                           self.dparameters.get('master_hosts')[2], self.dparameters.get('passwordkey'))
			wtenantkey = 'hdbuserstore SET W{0} "{1}:3{2}13@{0}, {3}:3{2}13@{0}, {4}:3{2}13@{0}" SYSTEM {5};'.format(self.dparameters.get('tenantsid'), self.dparameters.get('master_hosts')[0], self.dparameters.get(
				'instance_number'), self.dparameters.get('master_hosts')[1], self.dparameters.get('master_hosts')[2], self.dparameters.get('passwordkey'))
			systemdbsapdbctrlkey = 'hdbuserstore SET {}SAPDBCTRL localhost:{} SAP_DBCTRL {}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			systemdbsapdbctrltenantkey = 'hdbuserstore SET {0}SAPDBCTRL{1} localhost:{2}@{1} SAP_DBCTRL {3}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'),
			                                                                                                        self.dparameters.get('passwordkey'))
			systemdbsapdbctrltenantportkey = 'hdbuserstore SET {0}SAPDBCTRL{1} localhost:{1} SAP_DBCTRL {2}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('tenantsqlport'), sys.argv())
			bkpmonkey = 'hdbuserstore SET BKPMON localhost:{} BKPMON {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			bladelogickey = 'hdbuserstore SET BLADELOGIC localhost:{} BLADELOGIC {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			bladelogictenantkey = 'hdbuserstore SET BLADELOGIC{0} localhost:{1}@{0} BLADELOGIC {2}'.format(self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			camkey = 'hdbuserstore SET CAM localhost:{} CAM_CHANGE {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			camtenantkey = 'hdbuserstore SET CAM{0} localhost:{1}@{0} CAM_CHANGE {2}'.format(self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))

			hdbuserstorecommands = {wkey, wtenantkey, systemdbsapdbctrlkey, systemdbsapdbctrltenantkey, systemdbsapdbctrltenantportkey, bkpmonkey, bladelogickey, bladelogictenantkey, camkey, camtenantkey}
			for cmd in hdbuserstorecommands:
				subprocess.call(cmd, shell=True)

			subprocess.call(['hdbuserstore list'], shell=True)

		elif self.has_replication & self.is_multi_node is not True:
			wkey = 'hdbuserstore SET W localhost:{} SYSTEM {};'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			wtenantkey = 'hdbuserstore SET W{0} localhost:{1}@{0} SYSTEM {2};'.format(self.dparameters.get('tenantsid'), self.dparameters.get('tenantsqlport'), self.dparameters.get('passwordkey'))
			systemdbsapdbctrlkey = 'hdbuserstore SET {}SAPDBCTRL localhost:{} SAP_DBCTRL {}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			systemdbsapdbctrltenantkey = 'hdbuserstore SET {}SAPDBCTRL{} localhost:{}@{} SAP_DBCTRL {}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'),
			                                                                                                           self.dparameters.get('tenantsid'), self.dparameters.get('passwordkey'))
			systemdbsapdbctrltenantportkey = 'hdbuserstore SET {0}SAPDBCTRL{1} localhost:{1} SAP_DBCTRL {2}'.format(self.dparameters.get('systemdbsid'), self.dparameters.get('tenantsqlport'), self.dparameters.get('passwordkey'))
			bkpmonkey = 'hdbuserstore SET BKPMON localhost:{} BKPMON {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			bladelogickey = 'hdbuserstore SET BLADELOGIC localhost:{} BLADELOGIC {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			bladelogictenantkey = 'hdbuserstore SET BLADELOGIC{} localhost:{}@{} BLADELOGIC {}'.format(self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('tenantsid'), self.dparameters.get(
				'passwordkey'))
			camkey = 'hdbuserstore SET CAM localhost:{} CAM_CHANGE {}'.format(self.dparameters.get('systemdbsqlport'), self.dparameters.get('passwordkey'))
			camtenantkey = 'hdbuserstore SET CAM{} localhost:{}@{} CAM_CHANGE {}'.format(self.dparameters.get('tenantsid'), self.dparameters.get('systemdbsqlport'), self.dparameters.get('tenantsid'), self.dparameters.get('passwordkey'))

			hdbuserstorecommands = {wkey, wtenantkey, systemdbsapdbctrlkey, systemdbsapdbctrltenantkey, systemdbsapdbctrltenantportkey, bkpmonkey, bladelogickey, bladelogictenantkey, camkey, camtenantkey}
			for cmd in hdbuserstorecommands:
				subprocess.call(cmd, shell=True)

			subprocess.call(['hdbuserstore list'], shell=True)

	def create_hdb_user_store_hana_non_mdc(self):

		if self.has_replication & self.is_multi_node:
			wkey = 'hdbuserstore SET W "{0}:{1}, {2}:{1}, {3}:{1}" SYSTEM {4};'.format(self.dparameters.get('master_hosts')[0], self.dparameters.get('sqlport'), self.dparameters.get('master_hosts')[1], self.dparameters.get(
				'master_hosts')[2], self.dparameters.get('password'))
			sapdbctrlkey = 'hdbuserstore SET {0}SAPDBCTRL localhost:{1} SAP_DBCTRL {2};'.format(self.dparameters.get('sid'), self.dparameters.get('sqlport'), self.dparameters.get('password'))
			bkpmonkey = 'hdbuserstore SET BKPMON localhost:{0} BKPMON {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))
			bladelogickey = 'hdbuserstore SET BLADELOGIC localhost:{0} BLADELOGIC {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))
			camkey = 'hdbuserstore SET CAM localhost:{0} CAM_CHANGE {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))

			hdbuserstorecommands = {wkey, sapdbctrlkey, bkpmonkey, bladelogickey, camkey}
			for cmd in hdbuserstorecommands:
				subprocess.call(cmd, shell=True)

			subprocess.call(['hdbuserstore list'], shell=True)

		elif self.has_replication is True & self.is_multi_node is not True:
			wkey = 'hdbuserstore SET W "{0}:{1}, {2}:{1}, {3}:{1}" SYSTEM {4};'.format(self.dparameters.get('master_hosts')[0], self.dparameters.get('sqlport'), self.dparameters.get('master_hosts')[1], self.dparameters.get(
				'master_hosts')[2], self.dparameters.get('password'))
			sapdbctrlkey = 'hdbuserstore SET {0}SAPDBCTRL localhost:{1} SAP_DBCTRL {2};'.format(self.dparameters.get('sid'), self.dparameters.get('sqlport'), self.dparameters.get('password'))
			bkpmonkey = 'hdbuserstore SET BKPMON localhost:{0} BKPMON {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))
			bladelogickey = 'hdbuserstore SET BLADELOGIC localhost:{0} BLADELOGIC {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))
			camkey = 'hdbuserstore SET CAM localhost:{0} CAM_CHANGE {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))

			hdbuserstorecommands = {wkey, sapdbctrlkey, bkpmonkey, bladelogickey, camkey}
			for cmd in hdbuserstorecommands:
				subprocess.call(cmd, shell=True)

			subprocess.call(['hdbuserstore list'], shell=True)

		elif self.has_replication is not True & self.is_multi_node is True:
			wkey = 'hdbuserstore SET W "{0}:{1}, {2}:{1}, {3}:{1}" SYSTEM {4};'.format(self.dparameters.get('master_hosts')[0], self.dparameters.get('sqlport'), self.dparameters.get('master_hosts')[1], self.dparameters.get(
				'master_hosts')[2], self.dparameters.get('password'))
			sapdbctrlkey = 'hdbuserstore SET {0}SAPDBCTRL localhost:{1} SAP_DBCTRL {2};'.format(self.dparameters.get('sid'), self.dparameters.get('sqlport'), self.dparameters.get('password'))
			bkpmonkey = 'hdbuserstore SET BKPMON localhost:{0} BKPMON {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))
			bladelogickey = 'hdbuserstore SET BLADELOGIC localhost:{0} BLADELOGIC {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))
			camkey = 'hdbuserstore SET CAM localhost:{0} CAM_CHANGE {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))

			hdbuserstorecommands = {wkey, sapdbctrlkey, bkpmonkey, bladelogickey, camkey}
			for cmd in hdbuserstorecommands:
				subprocess.call(cmd, shell=True)

			subprocess.call(['hdbuserstore list'], shell=True)

		elif self.has_replication & self.is_multi_node is not True:
			wkey = 'hdbuserstore SET W localhost:{} SYSTEM {};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))
			sapdbctrlkey = 'hdbuserstore SET {0}SAPDBCTRL localhost:{1} SAP_DBCTRL {2};'.format(self.dparameters.get('sid'), self.dparameters.get('sqlport'), self.dparameters.get('password'))
			bkpmonkey = 'hdbuserstore SET BKPMON localhost:{0} BKPMON {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))
			bladelogickey = 'hdbuserstore SET BLADELOGIC localhost:{0} BLADELOGIC {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))
			camkey = 'hdbuserstore SET CAM localhost:{0} CAM_CHANGE {1};'.format(self.dparameters.get('sqlport'), self.dparameters.get('password'))

			hdbuserstorecommands = {wkey, sapdbctrlkey, bkpmonkey, bladelogickey, camkey}
			for cmd in hdbuserstorecommands:
				subprocess.call(cmd, shell=True)

			subprocess.call(['hdbuserstore list'], shell=True)


def main():

	if os.getlogin() == 'root':
		sys.exit("You must be authenticated with <sid>adm user in order to run the script")
	if len(sys.argv) == 2:
		ohana = HDBUserStoreClass(sys.argv[1])
	else:
		sys.exit("You must pass only one parameter to the script, which is the password for the HDBuserstore keys")


if __name__ == '__main__': main()
