"""
Unregister agent.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import sys

#get the exe path, which is the absolute path to the parent directory of the module's direcotry
exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/') + 1]

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
sys.path.insert(0, exe_path + 'lib/websocket_client') 
sys.path.insert(0, exe_path + 'src')
sys.path.insert(0, exe_path + 'lib')

#to avoid the bug reported at http://bugs.python.org/issue13684 we use a stable httplib version available with CPython 2.7.3
#since httplib has been renamed to http, we have to add that also in the path so that import can find it
if sys.version_info[0] == 3:
    sys.path.insert(0, exe_path + 'lib/httplib')

import exit_status

try:  #it is possible that the agent was removed from the UI, in that case it already had removed config files. so import api can raise an exception
    import api
    api.create_session()
except:
    sys.exit(exit_status.AGENT_ERR_SUCCESS)  #any exception should be considered as success

api.session.ping()  #required to set the post event, as the post event is set only after auth
status = api.session.unregister()  #unregister the agent
sys.exit(exit_status.AGENT_ERR_SUCCESS if api.is_not_connected(status) == False else exit_status.AGENT_ERR_FAILED_CONNECT)

