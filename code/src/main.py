__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import sys
import logging
import logging.handlers

exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/') + 1]
sys.path.insert(0, exe_path + 'lib/socketio_client') 
sys.path.insert(0, exe_path + 'lib/websocket_client')
sys.path.insert(0, exe_path + 'src')
sys.path.insert(0, exe_path + 'lib')

if sys.version_info[0] == 3:
    sys.path.insert(0, exe_path + 'lib/httplib')

import helper
import controller
import api
import exit_status
from globals import Globals

_log = logging.getLogger(__name__)

logging_list = []
logging_level = logging.INFO
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
    api.create_session()
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
    
    if temp == 'error':
        logging_level = logging.ERROR
    elif temp == 'debug':
        logging_level = logging.DEBUG
    elif temp == 'none':
        logging_list = []
except:
    logging_list = ['all']

for handler in logging.root.handlers:    
    if len(logging_list) != 1 or logging_list[0] != 'all':
        handler.addFilter(LoggingList(*logging_list))
        
if hasattr(globals.config.agent, '_id') == False:   
    if api.session.register(retry_count = 2, retry_interval = 10) != api.Status.SUCCESS:
        sys.exit(exit_status.AGENT_ERR_FAILED_REGISTER)
        
logger.setLevel(logging_level)

for handler in logging.root.handlers:
    handler.setFormatter(formatter)
               
def run(is_update_only_mode = False): 
    os.nice(19)
    globals.is_update_only_mode = is_update_only_mode
    controller.start()
    
if __name__ == "__main__":
    run()
