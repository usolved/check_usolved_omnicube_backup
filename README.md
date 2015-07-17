# check_usolved_omnicube_backup

## Overview

This Python Nagios plugin checks for any failed VM backups on SimpliVity Omnicubes. 
There's also a second mode in this plugin to display all VMs with a specific backup policiy.

## Authors

Ricardo Klement (www.usolved.net)

## Installation

Just copy the file check_usolved_omnicube_backup.py into your Nagios plugin directory.
For example this path: /usr/local/nagios/libexec/

Give check_usolved_omnicube_backup.py execution rights for the nagios user.
This plugin needs Python 2 to be installed.

Because this plugin uses SSH to connect to the OmniCube you need the Python module "pexpect" installed which contains "pxssh".

<pre><code>
sudo yum install pexpect.noarch
</code></pre>
or
<pre><code>
sudo apt-get install python-pexpect
</code></pre>

Why not Python 3 you may ask?
Most Nagios / Icinga installations are already using other plugins which are written in Python 2.
So for compatibility reasons I've decided to use Python 2 as well.


## Usage

### Test on command line
If you are in the Nagios plugin directory execute this command:

<pre><code>
./check_usolved_omnicube_backup.py -H ip_address_of_omnicube -U "domain\\\myuser" -P yourpassword -M status
</code></pre>

This should output something like this:

<pre><code>
OK - All backups were successful
</code></pre>

Here are all arguments that can be used within this plugin:

<pre><code>
-H &lt;host address&gt;
Give the host address of an OmniCube with the IP address or FQDN

-U &lt;ssh user&gt;
OmniCube SSH username (remember to escape the backslash in the username. For example domain\myuser would be "domain\\\myuser" or domain\\\\myuser as argument)

-P &lt;ssh password&gt;
OmniCube SSH password

-M &lt;mode&gt;
Plugin mode (-M status (to check if all backups were successful) or -M policy (to check if all VMs have policies assigned))

[-N &lt;policy name&gt;]
When you use -M policy then you have to set the policy name here

[-E &lt;exclude VMs&gt;]
Optional: Exclude comma separated hosts from the check for policy check

[-D &lt;backup date&gt;]
Optional: Without an argument the backups status check gets the status from yesterday.
If you wish to check for other time ranges, give the argument -D YYYY-MM-DD

[-T &lt;timeout&gt;]
Optional: SSH timeout in seconds. Default is 45 seconds.
</code></pre>

### Install in Nagios

Edit your **commands.cfg** and add the following.

Example for checking the backup status:

<pre><code>
define command {
    command_name    check_usolved_omnicube_backup_status
    command_line    $USER1$/check_usolved_omnicube_backup.py -H $HOSTADDRESS$ -U $ARG1$ -P $ARG2$ -M status
}
</code></pre>

Example for checking the assigned backup policies:

<pre><code>
define command {
    command_name    check_usolved_omnicube_backup_policy
    command_line    $USER1$/check_usolved_omnicube_backup.py -H $HOSTADDRESS$ -U $ARG1$ -P $ARG2$ -M policy -N policyname -E $ARG3$
}
</code></pre>

Edit your **services.cfg** and add the following.

Example for checking the backup status:

<pre><code>
define service{
	host_name				Test-Server
	service_description		OmniCube-Backup-Status
	use						generic-service
	check_command			check_usolved_omnicube_backup_status!domain\\\\username!password
}
</code></pre>

Example for checking the assigned backup policies:

<pre><code>
define service{
	host_name				Test-Server
	service_description		OmniCube-Backup-Policies
	use						generic-service
	check_command			check_usolved_omnicube_backup_policy!domain\\\\username!password!hostnotwant1,hostnotwant2
}
</code></pre>

You could also use host macros for the username and password.
Again: Pay attention for escaping the domain and username with the backslashes.
If you use a frontend like Centreon you need to put 4 backslashes between the domain and username.

Don't worry if the check takes a while for returning the info. The OmniCube SSH commands will take a while for executing.


### Errors you may encounter

If you get some cryptic erorrs with pxssh on CentOS 6 you need to edit the fallowing file:

<pre><code>
vi /usr/lib/python2.6/site-packages/pxssh.py
</code></pre>


Add the following lines of code:

<pre><code>
self.sendline() #Line 134
time.sleep(0.5) #Line 135
</code></pre>


Should be inserted  above the fallowing line:

<pre><code>
self.read_nonblocking(size=10000,timeout=1) # GAS: Clear out the cache before getting the prompt
</code></pre>
