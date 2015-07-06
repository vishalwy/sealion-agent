#!/usr/bin/env python

"""
Start script for agent.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import os

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]
sys.path.insert(0, exe_path + '/src')
sys.path.insert(0, exe_path + '/lib')
sys.path.insert(0, exe_path + '/lib/socketio_client') 
sys.path.insert(0, exe_path + '/lib/websocket_client')
sys.path.insert(0, exe_path + '/opt')

if len(sys.argv) == 2 and sys.argv[1] == 'debug':
    import main as main_module
else:
    import service as main_module
    
main_module.run()

