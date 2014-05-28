__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import sys

exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/') + 1]
sys.path.insert(0, exe_path + 'lib/websocket_client') 
sys.path.insert(0, exe_path + 'src')
sys.path.insert(0, exe_path + 'lib')

import exit_status

try:
    import api
    api.create_session()
except:
    sys.exit(exit_status.AGENT_ERR_SUCCESS)

api.session.ping()
status = api.session.unregister()
sys.exit(exit_status.AGENT_ERR_SUCCESS if api.is_not_connected(status) == False else exit_status.AGENT_ERR_FAILED_CONNECT)

