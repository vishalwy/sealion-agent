#!/usr/bin/env python

"""
Unregister agent.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import sys

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]
sys.path.insert(0, exe_path + '/lib/socketio_client') 
sys.path.insert(0, exe_path + '/lib/websocket_client')
sys.path.insert(0, exe_path + '/lib')
sys.path.insert(0, exe_path + '/src')

import exit_status

#whether to disable SSL verification; refer lib/request/__init__.py
if len(sys.argv) == 2 and sys.argv[1] == '--insecure':
    __insecure_ssl__ = True

try:  #it is possible that the agent was removed from the UI, in that case it already had removed config files. so import api can raise an exception
    import api
    api.create_session()
except:
    sys.exit(exit_status.AGENT_ERR_SUCCESS)  #any exception should be considered as success

status = api.session.unregister()  #unregister the agent
sys.exit(exit_status.AGENT_ERR_SUCCESS if api.is_not_connected(status) == False else exit_status.AGENT_ERR_FAILED_CONNECT)

