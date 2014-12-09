#!/usr/bin/env python

'''
This Python Nagios plugin checks for any failed VM backups on SimpliVity Omnicubes.
There's also a second mode in this plugin to check if all VMs have assigned backup policies.

Copyright (c) 2014 www.usolved.net 
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
parser.add_option('-M', '--mode', help='Plugins mode (-M status (to check if all backups were successful) or -M policy (to check if all VMs have policies assigned))', dest='arg_mode', type='string')
parser.add_option('-E', '--exclude', help='Exclude comma separated hosts for policy check', dest='arg_exclude', type='string', default='')
parser.add_option('-D', '--backupdate', help='Without an argument the backups status check gets the status from yesterday. If you wish to check for other days, give the argument -D YYYY-MM-DD', dest='arg_backupdate', type='string', default='yesterday')
parser.add_option('-T', '--timeout', help='SSH timeout in seconds', dest='arg_timeout', type='int', default=45)
(opts, args) = parser.parse_args()

arg_hostname 		= opts.arg_hostname
arg_username		= opts.arg_username
arg_password		= opts.arg_password
arg_mode			= opts.arg_mode
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


####################################################

def ssh_connect(hostname, username, password, timeout):

	global return_msg

	try:
		ssh = pxssh.pxssh(timeout=timeout)
		ssh.login(hostname, username, password)
		ssh.prompt()
		return ssh

	except pxssh.ExceptionPxssh, e:
		return_msg = "Unknown - pxssh failed on login. "
		return_msg += str(e)
		output_nagios(return_msg,'',return_code['UNKNOWN'])

def ssh_logout():
	ssh.logout()


####################################################

def get_failed_backups():

	if arg_backupdate == "yesterday":
		time_current 			= int(time.time()) - 86400
		time_current_date	 	= datetime.datetime.fromtimestamp(time_current).strftime('%Y-%m-%d')
	else:
		time_current_date = arg_backupdate

	ssh.sendline('svt-backup-show --status failed --output xml --since '+time_current_date)
	ssh.prompt()
	data = ssh.before
	data, rest = data.split('\n', 1) #strip out command itself
	#data = data.splitlines()
	return rest



def get_failed_backups_status(hosts_failed_backups):

	global return_msg

	return_hosts	= ''
	backup_status 	= 0

	try:
		hosts_failed_backups_xml = et.fromstring(hosts_failed_backups)
		for child in hosts_failed_backups_xml.findall('Backup'):

			failed_timestamp = int(child.find('timestamp').text)
			failed_timestamp = datetime.datetime.fromtimestamp(failed_timestamp).strftime('%Y-%m-%d %H:%M')

			return_hosts += child.find('hiveName').text+" ("+ str(failed_timestamp)+"), "
			backup_status = 2


		if backup_status == 0:
			return_msg = 'OK - All backups were successful'
		else:
			return_hosts 	= return_hosts[:-2]
			return_msg 		= 'Critical - Backup for '+return_hosts+' failed'

		return backup_status
	except:
		return_msg = 'Unknown - Returned XML data is not valid'
		return 3

####################################################

def get_hosts_with_no_policy():
	ssh.sendline('svt-vm-show --output xml')
	ssh.prompt()
	data = ssh.before
	data, rest = data.split('\n', 1) #strip out command itself
	#data = data.splitlines()
	return rest


def get_hosts_with_no_policy_status(hosts_with_no_policy):

	global return_msg
	return_hosts		= ''
	no_policy_status 	= 0

	try:
		hosts_with_no_policy_xml = et.fromstring(hosts_with_no_policy)
		for child in hosts_with_no_policy_xml.findall('VM'):

			if child.find('policy').text == "empty":
				if child.find('platformName').text not in hosts_excluded:
					return_hosts += child.find('platformName').text+", "
					no_policy_status = 2		


		if no_policy_status == 0:
			return_msg = 'OK - Backup policies for all hosts are configured'
		else:
			return_hosts 	= return_hosts[:-2]
			return_msg 		= 'Critical - Backup policy for '+return_hosts+' is missing'

		return no_policy_status
	except:
		return_msg = 'Unknown - Returned XML data is not valid'
		return 3



######################################################################
# General


if arg_mode == "status":
	ssh 					= ssh_connect(arg_hostname, arg_username, arg_password, arg_timeout)
	hosts_failed_backups 	= get_failed_backups()

	backup_status 			= get_failed_backups_status(hosts_failed_backups)

	if backup_status == 0:
		output_nagios(return_msg,'',return_code['OK'])
	elif backup_status == 2:
		output_nagios(return_msg,'',return_code['CRITICAL'])
	else:
		output_nagios(return_msg,'',return_code['UNKNOWN'])

	#ssh_logout()
elif arg_mode == "policy":
	ssh 					= ssh_connect(arg_hostname, arg_username, arg_password, arg_timeout)
	hosts_with_no_policy 	= get_hosts_with_no_policy()

	no_policy_status 		= get_hosts_with_no_policy_status(hosts_with_no_policy)

	if no_policy_status == 0:
		output_nagios(return_msg,'',return_code['OK'])
	elif no_policy_status == 2:
		output_nagios(return_msg,'',return_code['CRITICAL'])
	else:
		output_nagios(return_msg,'',return_code['UNKNOWN'])

	#ssh_logout()
else:
	return_msg = 'Unknown - Please select a mode.\nType ./'+os.path.basename(__file__)+' --help for all options.'
	output_nagios(return_msg,'',return_code['UNKNOWN'])
