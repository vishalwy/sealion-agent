#!/usr/bin/env python

"""
Start script for agent.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import os
import getopt
import signal

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]
sys.path.insert(0, exe_path + '/lib/socketio_client') 
sys.path.insert(0, exe_path + '/lib/websocket_client')
sys.path.insert(0, exe_path + '/opt/default/python/')
sys.path.insert(0, exe_path + '/lib')
sys.path.insert(0, exe_path + '/src')

import version_info
import exit_status

try:
    #try parsing the options
    options, args = getopt.getopt(sys.argv[1:], '', ['insecure', 'version', 'debug'])  
    options = [option[0] for option in options]
except Exception:
    options, args = [], sys.argv[1:]  #reset the options so that the service module takes care 
    
#whether to disable SSL verification; refer lib/request/__init__.py
if '--insecure' in options:
    __insecure_ssl__ = True
    
signal.signal(signal.SIGINT, lambda x, y: sys.exit(exit_status.AGENT_ERR_INTERRUPTED))  #setup signal handling for SIGINT
    
if '--version' in options:  #print version and exit
    version_info.print_version()
    sys.exit()  
elif '--debug' in options and len(args) == 1 and args[0] == 'start':
    #do not detach the process from the controlling terminal; so use main module
    import main as main_module
else:
    import service as main_module  #normal startup
    
main_module.run(*(tuple(args)))  #run the selected module with the arguments
