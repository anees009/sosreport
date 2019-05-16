''' The script does the following
1. Takes input from config file
2. prompts for repo password on the command lne
3. Checks for a directory in the qe repo and creates one if not exists
4. Generates sos reports sequencially from all servers
5. copies these report on local system (for local copy)
6. Uploads the files to remote qe repo system
7. compares checksum for these files'''
import os
import sys
import re
import getpass
import yaml
from glusto.core import Glusto as g

def parser(yaml_file):
	with open(yaml_file, 'r') as stream:
		data_loaded = yaml.load(stream, Loader=yaml.FullLoader)
		if isinstance(data_loaded, dict):
			return data_loaded
		else:
			print("Incorrect yaml file")
			sys.exit(0)

def main():
	if len(sys.argv) == 2:
		yaml_file = sys.argv[1]
	else:
		print("Kindly provide yaml file")
		sys.exit(0)

	config_dict = parser(yaml_file)
	servers = config_dict.get('servers')
	qe_repo = config_dict.get('repo')
	qe_host, qe_host_path = qe_repo[0].split(':')

	# Local path for sos-report
	dir_path = os.path.dirname(os.path.realpath(__file__))+ '/sosreport'
	try:
	    os.stat(dir_path)
	except:
	    os.mkdir(dir_path)

	# Create dir in qe repo
	# Using sshpass as the default repo has blocked passwordless login
	try: 
		p = getpass.getpass(prompt="Enter password for host %s \n" % qe_host) 
	except Exception as error: 
		print('ERROR', error) 

	command = 'sshpass -p %s ssh qe@%s "mkdir -p %s"' % (p, qe_host, qe_host_path)
	ret, _, err = g.run_local(command)
	
	print("Starting to generate sos-report")
	for server in servers:
		# generate sos-report
		ret, output, err = g.run(server, "echo -ne '\n\n' | sosreport")
		assert(ret==0), "Failed to generate sosreport for %s" % server
		remote_file_path = re.findall(r'/var/tmp/sosreport[^\s]+', output)[0]
		sosreport = remote_file_path.split('/tmp/')[1]
		remote_file_checksum = re.search(r'The checksum is: (\S+)', output).group(1)

		# Download sos-report to local system
		g.download(server, remote_file_path, dir_path)
		local_file_path = dir_path + '/' + sosreport

		# Upload sos-report to repo
		# Using sshpass as the default repo has blocked passwordless login
		command = 'sshpass -p %s scp -r %s qe@%s' % (p, local_file_path, qe_repo[0])
		ret, _, err = g.run_local(command)
		# Getting md5sum of the report from remote repo
		command = ('sshpass -p %s ssh qe@%s "md5sum %s/%s"' % (p, qe_host, qe_host_path, sosreport))
		ret, output, err = g.run_local(command)
		md5sum = output.split(" ")[0]

		# Match the md5sum with that of original 
		if remote_file_checksum == md5sum:
			print("Sos-report %s copied successfully and checksum matches" % sosreport)
		else:
			print("checksum match failed for %s" % sosreport)
			exit()
		
# Change permissions of qe repo

	command = ('sshpass -p %s ssh qe@%s "chmod -R 755 %s"' % (p, qe_host, qe_host_path))
	ret, output, err = g.run_local(command)
	assert(ret==0), "Failed to change permission for %s" % qe_host_path
	print("Successfully changed permissions for  %s:%s" % (qe_host, qe_host_path))

if __name__ == '__main__':
	main()
