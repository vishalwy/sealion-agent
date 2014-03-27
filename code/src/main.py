__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import sys
import threading
import logging
import logging.handlers
import linecache
import re

exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/') + 1]
sys.path.insert(0, exe_path + 'lib/socketio_client') 
sys.path.insert(0, exe_path + 'lib/websocket_client')
sys.path.insert(0, exe_path + 'src')
sys.path.insert(0, exe_path + 'lib')

import helper
import controller
import api
import exit_status
from globals import Globals

_log = logging.getLogger(__name__)

logging_list = []
logging_level = logging.NOTSET
logging.basicConfig(level = logging_level, format = '%(message)s')
formatter = logging.Formatter('%(asctime)-15s %(levelname)-7s %(thread)d - %(module)-s[%(lineno)-d]: %(message)s')
logger = logging.getLogger()

try:
    lf = logging.handlers.RotatingFileHandler(helper.Utils.get_safe_path(exe_path + 'var/log/sealion.log'), maxBytes = 1024 * 1024 * 100, backupCount = 5)
    lf.setFormatter(formatter)
    logger.addHandler(lf)
except Exception as e:
    sys.stderr.write('Failed to open the log file; %s\n' % str(e))
    sys.exit(exit_status.AGENT_ERR_FAILED_OPEN_LOG)
    
try:
    globals = Globals()
    api = api.API()
except Exception as e:
    _log.error(str(e))
    sys.exit(exit_status.AGENT_ERR_FAILED_INITIALIZE)
    
class LoggingList(logging.Filter):
    def __init__(self, *logs):
        self.logs = [logging.Filter(log) for log in logs]

    def filter(self, record):
        return any(log.filter(record) for log in self.logs)
    
try:
    logging_list = globals.config.sealion.logging['modules']
except:
    pass

try:
    temp = globals.config.sealion.logging['level'].strip()
    is_trace = False
    
    if temp == 'error':
        logging_level = logging.ERROR
    elif temp == 'info':
        logging_level = logging.INFO
    elif temp == 'debug':
        logging_level = logging.DEBUG
    elif temp == 'none':
        logging_list = []
    elif temp == 'trace':
        is_trace = True
        logging_level = logging.DEBUG        
except:
    logging_list = []

for handler in logging.root.handlers:    
    if len(logging_list) != 1 or logging_list[0] != 'all':
        handler.addFilter(LoggingList(*logging_list))
        
if hasattr(globals.config.agent, '_id') == False:   
    if api.register(retry_count = 2, retry_interval = 10) != api.status.SUCCESS:
        sys.exit(exit_status.AGENT_ERR_FAILED_REGISTER)
        
for handler in logging.root.handlers:
    handler.setLevel(logging_level)
    handler.setFormatter(formatter)

def traceit(frame, event, arg):
    if event == "line":
        lineno = frame.f_lineno
        filename = frame.f_globals.get("__file__")
        
        if filename == None:
            return traceit
        
        if (filename.endswith(".pyc") or
            filename.endswith(".pyo")):
            filename = filename[:-1]
        name = frame.f_globals["__name__"]
        
        if (re.match('^(logging.*|main|\_\_main\_\_|threading|posixpath|genericpath)$', name) == None and (name in logging_list or (len(logging_list) == 1 and logging_list[0] == 'all'))):
            line = linecache.getline(filename, lineno)
            _log.log(5, "%s[%d]: %s" % (name, lineno, line.rstrip()))
    return traceit

if is_trace == True:
    try:
        lf = logging.handlers.RotatingFileHandler(helper.Utils.get_safe_path(exe_path + 'var/log/trace.log'), maxBytes = 1024 * 1024 * 100, backupCount = 5)
        
        if len(logging_list) != 1 or logging_list[0] != 'all':
            lf.addFilter(LoggingList(*logging_list))
            
        formatter = logging.Formatter('%(asctime)-15s TRACE   %(thread)d - %(message)s')
        lf.setFormatter(formatter)
        sys.settrace(traceit)
        threading.settrace(traceit)
        lf.setLevel(5)
        logger.addHandler(lf)
    except:
        pass
               
def start(is_update_only_mode = False): 
    os.nice(19)
    globals.is_update_only_mode = is_update_only_mode
    controller.start()

if __name__ == "__main__":
    start()
