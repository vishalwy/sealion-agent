#!/usr/bin/env python

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
    
#Python version check. SeaLion agent works only with Python version >= 2.6
if float('%d.%d' % (sys.version_info[0], sys.version_info[1])) < 2.6:
    sys.stderr.write('SeaLion agent requires python version 2.6 or above\n')
    sys.exit(ERR_INCOMPATIBLE_PYTHON)
    
try:
    import os.path
except Exception:
    e = sys.exc_info()[1]
    sys.stderr.write(unicode(e) + '\n')
    sys.exit(ERR_FAILED_DEPENDENCY)
    
#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]
sys.path.insert(0, exe_path + '/lib/socketio_client') 
sys.path.insert(0, exe_path + '/lib/websocket_client')
sys.path.insert(0, exe_path + '/lib')
    
from constructs import unicode
error = False  #any errors

#modules to be checked for
#a module can provide alternative modules by enclosing them in a list
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
    'platform', 
    'multiprocessing', 
    'traceback', 
    'logging.handlers',
    'gc',
    'pwd',
    'getopt',
    'tempfile',
    'sqlite3',
    'ssl',
    ['queue', 'Queue'],
    'zlib',
    ['websocket3', 'websocket2'],
    'socketio_client'
]

for module in modules:
    if type(module) is list:
        module_list = module
    else:
        module_list = [module]
    
    module_list_count, i = len(module_list), 0

    while i < module_list_count:
        try:
            __import__(module_list[i])  #try to import the module
            break
        except:
            #if this is the last alternative available; then catch the error
            if i + 1 == module_list_count:
                e = sys.exc_info()[1]
                error = True
                sys.stderr.write(unicode(e) + '\n')
                
        i += 1

error and sys.exit(ERR_FAILED_DEPENDENCY)
sys.stdout.write('Success\n')
sys.exit(ERR_SUCCESS)

