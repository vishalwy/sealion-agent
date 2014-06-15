#!/usr/bin/python

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
ERR_SUCCESS = 0
ERR_INCOMPATIBLE_PYTHON = 2
ERR_FAILED_DEPENDENCY = 3
PADDING = '       '

if float('%d.%d' % (sys.version_info[0], sys.version_info[1])) < 2.6:
    sys.stderr.write(PADDING + 'SeaLion agent requires python version 2.6 or above\n')
    sys.exit(ERR_INCOMPATIBLE_PYTHON)
    
try:
    import os.path
except Exception as e:
    sys.stderr.write(str(e) + '\n')
    sys.exit(ERR_FAILED_DEPENDENCY)
    
exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/') + 1]
sys.path.insert(0, exe_path + 'lib/socketio_client') 
sys.path.insert(0, exe_path + 'lib/websocket_client')
sys.path.insert(0, exe_path + 'lib')

if sys.version_info[0] == 3:
    sys.path.insert(0, exe_path + 'lib/httplib')    
    
api_url = "<api-url>"
errors = []
modules = [
    'os', 
    'logging', 
    'subprocess', 
    'time', 
    'json', 
    're', 
    'threading', 
    'signal', 
    'atexit', 
    'os.path', 
    'platform', 
    'multiprocessing', 
    'traceback', 
    'logging.handlers',
    'gc',
    'pwd',
    'tempfile',
    'sqlite3',
    'ssl',
    'socketio_client',
    'requests'
]

for module in modules:
    try:
        __import__(module)
    except (ImportError, TypeError, AttributeError) as e:
        errors.append(str(e))
    except:
        pass
    
try:
    __import__('queue')
except ImportError:
    try:
        __import__('Queue')
    except ImportError as e:
        errors.append(str(e))

try:
    proxies = {'https': sys.argv[1]} if len(sys.argv) == 2 else {}
    requests.get(api_url, proxies = proxies, timeout = 10)
except (ImportError, TypeError, AttributeError) as e:
    errors.append(str(e))
except:
    pass

if len(errors):
    sys.stderr.write(PADDING + ('\n' + PADDING).join(errors) + '\n')
    sys.exit(ERR_FAILED_DEPENDENCY)

sys.stdout.write('Success\n')
sys.exit(ERR_SUCCESS)

