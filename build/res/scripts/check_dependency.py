#!/usr/bin/python

"""
Script to perform dependency check for SeaLion agent.
It checks for any missing module in the Python version.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
ERR_SUCCESS = 0
ERR_INCOMPATIBLE_PYTHON = 2
ERR_FAILED_DEPENDENCY = 3
ERR_INVALID_USAGE=7

#Python 2.x vs 3.x
try:
    unicode = unicode
except:
    def unicode(object, *args, **kwargs):
        return str(object)
    
i, arg_len, padding, proxies = 0, len(sys.argv), '', {}

try:
    while i < arg_len:  #read all the arguments
        if not i:  #skip the first argument as it is the name of the script
            i += 1
            continue

        if sys.argv[i] == '-x':
            i += 1
            proxies = {'https': sys.argv[i]}
        elif sys.argv[i] == '-p':
            i += 1
            padding = sys.argv[i]
            
        i += 1
except IndexError:
    sys.stderr.write('Error: ' + sys.argv[i - 1] + ' requires an argument\n')
    sys.exit(ERR_INVALID_USAGE)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')
    sys.exit(ERR_INVALID_USAGE)

if float('%d.%d' % (sys.version_info[0], sys.version_info[1])) < 2.6:
    sys.stderr.write(padding + 'SeaLion agent requires python version 2.6 or above\n')
    sys.exit(ERR_INCOMPATIBLE_PYTHON)
    
try:
    import os.path
except Exception:
    e = sys.exc_info()[1]
    sys.stderr.write(unicode(e) + '\n')
    sys.exit(ERR_FAILED_DEPENDENCY)
    
exe_path = os.path.dirname(os.path.abspath(__file__))

if exe_path[len(exe_path) - 1] == '/':
    exe_path = exe_path[:-1]
    
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
    except (ImportError, TypeError, AttributeError):
        e = sys.exc_info()[1]
        errors.append(unicode(e))
    except:
        pass
    
try:
    __import__('queue')
except ImportError:
    try:
        __import__('Queue')
    except ImportError:
        e = sys.exc_info()[1]
        errors.append(unicode(e))

try:
    requests.get(api_url, proxies = proxies, timeout = 10)
except (ImportError, TypeError, AttributeError):
    e = sys.exc_info()[1]
    errors.append(unicode(e))
except:
    pass

if len(errors):
    sys.stderr.write(padding + ('\n' + padding).join(errors) + '\n')
    sys.exit(ERR_FAILED_DEPENDENCY)

sys.stdout.write('Success\n')
sys.exit(ERR_SUCCESS)

