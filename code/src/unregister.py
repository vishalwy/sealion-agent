import os
import sys

exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/') + 1]
sys.path.append(exe_path + 'src')
sys.path.append(exe_path + 'lib')
sys.path.append(exe_path + 'lib/websocket_client') 

from globals import Globals

try:
    globals = Globals()
except:
    sys.exit(0)

globals.api.ping()
status = globals.api.unregister()
sys.exit(0 if globals.api.is_not_connected(status) == False else 1)

