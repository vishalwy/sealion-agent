__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__license__ = 'GPL'
__email__ = 'support@sealion.com'

import os
import sys

exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/') + 1]
sys.path.insert(0, exe_path + 'lib/websocket_client') 
sys.path.insert(0, exe_path + 'src')
sys.path.insert(0, exe_path + 'lib')

try:
    from api import API
    api = API()
except:
    sys.exit(0)

api.ping()
status = api.unregister()
sys.exit(0 if api.is_not_connected(status) == False else 1)

