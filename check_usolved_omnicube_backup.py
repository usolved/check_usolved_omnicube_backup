#!/usr/bin/env python

'''
This Python Nagios plugin checks for any failed VM backups on SimpliVity OmniCube.
There's also a second mode in this plugin to display all VMs with a specific backup policiy.

Python 2 is required with use of the libraries sys, os, optparse, time, datetime, pxssh
Normally you just need to install "sudo yum install pexpect.noarch" or "sudo apt-get install python-pexpect"

Copyright (c) 2015 www.usolved.net 
Published under https://github.com/usolved/check_usolved_omnicube_backup


This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

------------------------

v1.4
The XML output has an extra line when too much results are found with the svt-backup-show. Added --max-results parameter to fix this.

v1.3
Added enhanced argument status:notstarted to check for not started backups (OmniCube command svt-backup-show just includes started backups)
Bugfix for parameter -D. The --until argument is now being used for the OmniCube command
Timeout parameter is now also being used for the OmniCube commands and not just the SSH connect

v1.2
Changed policy check that you can list hosts with a specific policy name

v1.1
Bugfix for the backup status. When the retried backup succeeded you'll get an OK status and an extended info which hosts needed more than one try

v1.0
Initial release

'''

import sys
import os
import optparse
import time
import datetime
import pxssh


try:
	import xml.etree.ElementTree as et
except ImportError:
	import elementtree.ElementTree as et


######################################################################
# Definitions of variables

#max results for svt-backup-show command
max_results 	= 10000


# Arrays for return codes and return message
return_code 	= { 'OK': 0, 'WARNING': 1, 'CRITICAL': 2, 'UNKNOWN': 3 }
return_msg 		= ''
return_perfdata = ''
hosts_excluded	= ''



######################################################################
# Parse Arguments
parser 		= optparse.OptionParser()
parser.add_option('-H', '--hostname', help='IP or hostname of the OmniCube host', dest='arg_hostname', type='string')
parser.add_option('-U', '--username', help='OmniCube SSH username (remember to escape the backslash in the username. For example domain\myuser would be "domain\\\\\myuser" or domain\\\\\\\myuser as argument)', dest='arg_username', type='string')
parser.add_option('-P', '--password', help='OmniCube SSH password', dest='arg_password', type='string')
parser.add_option('-M', '--mode', help='Plugins mode (-M status (to check if all backups were successful), -M status:notstarted (to check if all backups were successful including not started backups) or -M policy (to check if all VMs have policies assigned))', dest='arg_mode', type='string')
parser.add_option('-N', '--policyname', help='Backup policy name', dest='arg_policyname', type='string')
parser.add_option('-E', '--exclude', help='Exclude comma separated hosts for policy check', dest='arg_exclude', type='string', default='')
parser.add_option('-D', '--backupdate', help='Without an argument the backups status check gets the status from yesterday. If you wish to check for other days, give the argument -D YYYY-MM-DD', dest='arg_backupdate', type='string', default='yesterday')
parser.add_option('-T', '--timeout', help='SSH and OmniCube command timeout in seconds', dest='arg_timeout', type='int', default=45)
(opts, args) = parser.parse_args()

arg_hostname 		= opts.arg_hostname
arg_username		= opts.arg_username
arg_password		= opts.arg_password
arg_mode			= opts.arg_mode
arg_policyname		= opts.arg_policyname
arg_exclude			= opts.arg_exclude
arg_backupdate		= opts.arg_backupdate
arg_timeout			= opts.arg_timeout

if arg_exclude != "":
	hosts_excluded = arg_exclude.split(',')


######################################################################
# Functions

def output_nagios(return_msg, return_perfdata, return_code):
	print return_msg
	sys.exit(return_code)


#--------------------------------------------------------------------


def ssh_connect(hostname, username, password, timeout):

	global return_msg

	try:
		ssh = pxssh.pxssh(timeout=timeout)
		ssh.login(hostname, username, password)
		#ssh.prompt()
		return ssh

	except pxssh.ExceptionPxssh, e:
		return_msg = "Unknown - pxssh failed on login. "
		return_msg += str(e)
		output_nagios(return_msg,'',return_code['UNKNOWN'])

#--------------------------------------------------------------------


def ssh_logout():

	ssh.logout()


#--------------------------------------------------------------------


def get_failed_backups():

	if arg_backupdate == "yesterday":
		time_current 		= int(time.time()) - 86400

		time_since_date	 	= ' --since ' + datetime.datetime.fromtimestamp(time_current).strftime('%Y-%m-%d')
		time_until_date     = ''

	else:
		time_since_date 			= ' --since ' + arg_backupdate

		#convert to timestamp and add one day in seconds
		time_until_date_timestamp 	= int(time.mktime(datetime.datetime.strptime(arg_backupdate, "%Y-%m-%d").timetuple())) + 86400

		#convert timestamp back to yyyy-mm-dd
		time_until_date	 			= ' --until ' + datetime.datetime.fromtimestamp(time_until_date_timestamp).strftime('%Y-%m-%d')


	#strip out unnecessary xml tags to shrink the size
	ssh.sendline('svt-backup-show --output xml --max-results '+str(max_results)+' --timeout '+str(arg_timeout) + time_since_date + time_until_date+' | sed "/\(<dcId>\|<sentSize>\|<sourceVmDeploymentStatus>\|<name>\|<hiveId>\|<consistency>\|<consistent>\|<pedigree>\|<dsId>\|<expirationTime>\|<logicalSize>\|<lastTimeSizeCalc>\|<id>\|<backupId>\|<datastore>\|<vmDeleteTime>\|<percentComp>\|<vmRemovedTime>\|<percentTrans>\|<repTaskId>\|<dsRemoved>\|<datacenter>\|<uniqueSize>\)/d"')
	ssh.prompt()
	data = ssh.before

	data, rest = data.split('\n', 1) #strip out command itself



	return rest


#--------------------------------------------------------------------


def get_hosts_all():
	ssh.sendline('svt-vm-show --timeout '+str(arg_timeout)+' --output xml')
	ssh.prompt()
	data = ssh.before
	data, rest = data.split('\n', 1) #strip out command itself

	return rest


#--------------------------------------------------------------------


def get_failed_backups_status(hosts_failed_backups):

	global return_msg

	return_hosts			= ''
	return_hosts_retried	= ''
	backup_status 			= 0
	backup_success 			= []
	hosts_backup_started 	= []


	#--------------------------------------------------------------
	#list failed backups

	try:

		hosts_failed_backups_xml = et.fromstring(hosts_failed_backups)
		for child in hosts_failed_backups_xml.findall('Backup'):

			backup_state 	= int(child.find('state').text)
			backup_host 	= child.find('hiveName').text

			hosts_backup_started.append(backup_host)


			# if the state was successfull, add these hosts to array
			if backup_state == 4:

				backup_success.append(backup_host)

			# if backup failed go to this tree
			elif backup_state == 3:

				# if current host has not succeeded then mark them critical
				if backup_host not in backup_success:
					failed_timestamp = int(child.find('timestamp').text)
					failed_timestamp = datetime.datetime.fromtimestamp(failed_timestamp).strftime('%Y-%m-%d %H:%M')

					return_hosts += backup_host+" ("+ str(failed_timestamp)+"), "

					backup_status = 2

				# just add hosts for informational reasons
				else:
					return_hosts_retried += backup_host+", "

	except:

		return_msg = 'Unknown - Returned XML data for backup VMs is not valid. For example a missing root element or too much data.'
		return 3


	#--------------------------------------------------------------
	#Get all VMs because svt-backup-show doesn't list not started backups

	if arg_mode == "status:notstarted":

		try:

			hosts_all 		= get_hosts_all()

			hosts_all_xml = et.fromstring(hosts_all)
			for child in hosts_all_xml.findall('VM'):

				# also matches 'restore' when vm name is 'host_restore_01'
				if not any(host in child.find('platformName').text for host in hosts_excluded):

					current_host = child.find('platformName').text

					if current_host not in hosts_backup_started:

						return_hosts += current_host + " (not started), "
						backup_status = 2

		except:

			return_msg = 'Unknown - Returned XML data for all VMs is not valid. For example a missing root element or too much data.'
			return 3



	#--------------------------------------------------------------
	#evaluate return values for output

	if backup_status == 0:
		return_msg = 'OK - All backups were successful'
		if return_hosts_retried:
			return_msg += '\nHosts with more than one try for successful backup:\n'+return_hosts_retried[:-2]

	else:
		return_hosts 	= return_hosts[:-2] #delete last 2 characters
		return_msg 		= 'Critical - Backup failed for '+return_hosts

		if len(return_msg) > 250:
			return_msg_normal = return_msg[:250]
			return_msg_extended = return_msg[250:]
			return_msg = return_msg_normal+'...\n...'+return_msg_extended+'\n'

		if return_hosts_retried:
			return_msg += '\nHosts with more than one try for successful backup:\n'+return_hosts_retried[:-2]

	return backup_status



#--------------------------------------------------------------------


def get_hosts_with_policy_status(hosts_with_policy):

	global return_msg
	return_hosts		= ''
	hosts_found 		= 0

	if arg_policyname:

		try:
			hosts_with_policy_xml = et.fromstring(hosts_with_policy)
			for child in hosts_with_policy_xml.findall('VM'):

				if child.find('policy').text == arg_policyname:
					if child.find('platformName').text not in hosts_excluded:
						return_hosts += child.find('platformName').text+", "
						hosts_found = 1		


			if hosts_found == 0:
				return_msg = 'No hosts found with backup policy "'+arg_policyname+'"'
			else:
				return_hosts 	= return_hosts[:-2]
				return_msg 		= 'Hosts with backup policy "'+arg_policyname+'": '+return_hosts

			return 0
		except:
			return_msg = 'Unknown - Returned XML data is not valid'
			return 3
	else:
		return_msg = 'Unknown - No policy name given. Please add argument -N'
		return 3



######################################################################
# General


if arg_mode == "status" or arg_mode == "status:notstarted":

	ssh 					= ssh_connect(arg_hostname, arg_username, arg_password, arg_timeout)
	hosts_failed_backups 	= get_failed_backups()

	backup_status 			= get_failed_backups_status(hosts_failed_backups)

	ssh_logout()


	if backup_status == 0:
		output_nagios(return_msg,'',return_code['OK'])
	elif backup_status == 2:
		output_nagios(return_msg,'',return_code['CRITICAL'])
	else:
		output_nagios(return_msg,'',return_code['UNKNOWN'])



elif arg_mode == "policy":

	ssh 					= ssh_connect(arg_hostname, arg_username, arg_password, arg_timeout)
	hosts_with_policy 		= get_hosts_all()

	no_policy_status 		= get_hosts_with_policy_status(hosts_with_policy)

	ssh_logout()


	if no_policy_status == 0:
		output_nagios(return_msg,'',return_code['OK'])
	elif no_policy_status == 2:
		output_nagios(return_msg,'',return_code['CRITICAL'])
	else:
		output_nagios(return_msg,'',return_code['UNKNOWN'])


else:
	return_msg = 'Unknown - Please select a mode.\nType ./'+os.path.basename(__file__)+' --help for all options.'
	output_nagios(return_msg,'',return_code['UNKNOWN'])

