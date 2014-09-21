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

usage = 'Usage: check_dependency.py {[-x <proxy address>] [-p <padding for output>] [-a <api url>] | -h for Help}\n'

#Python 2.x vs 3.x
try:
    unicode = unicode
except:
    def unicode(object, *args, **kwargs):
        return str(object)
    
i, arg_len, padding, proxies, api_url = 1, len(sys.argv), '', {}, ''

try:
    while i < arg_len:  #read all the arguments
        if sys.argv[i] == '-x':  #proxy
            i += 1  #read option value
            proxies = {'https': sys.argv[i]}
        elif sys.argv[i] == '-p':  #padding for output
            i += 1  #read option value
            padding = sys.argv[i]
        elif sys.argv[i] == '-a':  #api url to test for connection tunneling
            i += 1  #read option value
            api_url = sys.argv[i]
        elif sys.argv[i] == '-h':  #help
            sys.stdout.write(usage)
            sys.exit(0)
            
        i += 1
except IndexError:
    sys.stderr.write('Error: %s requires an argument\n%s' % (sys.argv[i - 1], usage))  #missing option value
    sys.exit(ERR_INVALID_USAGE)
except Exception:
    e = sys.exc_info()[1]
    sys.stderr.write('Error: ' + unicode(e) + '\n')  #some error
    sys.exit(ERR_INVALID_USAGE)

#Python version check. SeaLion agent works only with Python version >= 2.6
if float('%d.%d' % (sys.version_info[0], sys.version_info[1])) < 2.6:
    sys.stderr.write(padding + 'SeaLion agent requires python version 2.6 or above\n')
    sys.exit(ERR_INCOMPATIBLE_PYTHON)
    
try:
    import os.path
except Exception:
    e = sys.exc_info()[1]
    sys.stderr.write(unicode(e) + '\n')
    sys.exit(ERR_FAILED_DEPENDENCY)
    
#get the exe path, which is the absolute path to the parent directory of the module's direcotry
exe_path = os.path.dirname(os.path.abspath(__file__))

if exe_path[len(exe_path) - 1] == '/':
    exe_path = exe_path[:-1]
    
exe_path = exe_path[:exe_path.rfind('/') + 1]

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
sys.path.insert(0, exe_path + 'lib/socketio_client') 
sys.path.insert(0, exe_path + 'lib/websocket_client')
sys.path.insert(0, exe_path + 'lib')

#to avoid the bug reported at http://bugs.python.org/issue13684 we use a stable httplib version available with CPython 2.7.3 and 3.2.3
#since httplib has been renamed to http, we have to add that also in the path so that import can find it
if sys.version_info[0] == 3:
    sys.path.insert(0, exe_path + 'lib/httplib')    
    
errors = []  #any errors

#modules to be checked for
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
        __import__(module)  #try to import the modules
    except (ImportError, TypeError, AttributeError):
        e = sys.exc_info()[1]
        errors.append(unicode(e))
    except:
        pass
    
#also import queue
try:
    __import__('queue')
except ImportError:
    try:
        __import__('Queue')
    except ImportError:
        e = sys.exc_info()[1]
        errors.append(unicode(e))

#check whether the connection tunneling works
try:
    api_url and requests.get(api_url, proxies = proxies, timeout = 10)
except (ImportError, TypeError, AttributeError):
    e = sys.exc_info()[1]
    errors.append(unicode(e))
except:
    pass

#display any errors
if len(errors):
    sys.stderr.write(padding + ('\n' + padding).join(errors) + '\n')
    sys.exit(ERR_FAILED_DEPENDENCY)

sys.stdout.write('Success\n')
sys.exit(ERR_SUCCESS)

