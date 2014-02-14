import gc
gc.set_threshold(500, 7, 7)

import os
import sys

exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path if (exe_path[len(exe_path) - 1] == '/') else (exe_path + '/')
sys.path.append(exe_path + 'lib')
sys.path.append(exe_path + 'src')
sys.path.append(exe_path + 'lib/websocket_client') 

import logging
import logging.handlers
import helper
import services
from globals import Globals

_log = logging.getLogger(__name__)

logging_list = []
logging_level = logging.INFO
logging.basicConfig(level = logging_level, format = '%(message)s')
formatter = logging.Formatter('%(asctime)-15s %(levelname)-7s %(thread)d - %(module)-s[%(lineno)-d]: %(message)s')
logger = logging.getLogger()

try:
    lf = logging.handlers.RotatingFileHandler(helper.Utils.get_safe_path(exe_path + 'var/log/sealion.log'), maxBytes = 1024 * 1024 * 100, backupCount = 10)
    lf.setFormatter(formatter)
    logger.addHandler(lf)
except Exception, e:
    sys.stderr.write('Failed to open log file; ' + str(e))
    sys.exit(0)
    
try:
    globals = Globals()
except Exception, e:
    _log.error(str(e))
    sys.exit(0)
    
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
    
    if temp == 'error':
        logging_level = logging.ERROR
    elif temp == 'debug':
        logging_level = logging.DEBUG
    elif temp == 'none':
        logging_list = []
except:
    logging_list = []

for handler in logging.root.handlers:    
    if len(logging_list) != 1 or logging_list[0] != 'all':
        handler.addFilter(LoggingList(*logging_list))
        
if hasattr(globals.config.agent, '_id') == False:   
    if globals.api.register(retry_count = 2, retry_interval = 10) != globals.APIStatus.SUCCESS:
        sys.exit(0)
        
logger.setLevel(logging_level)

for handler in logging.root.handlers:
    handler.setFormatter(formatter)
               
def start(is_update_only_mode = False): 
    globals.is_update_only_mode = is_update_only_mode
    services.start()

if __name__ == "__main__":
    start()
