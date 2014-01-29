#!/usr/bin/python
import sys
sys.path.append('lib')
sys.path.append('src')
sys.path.append('lib/websocket_client') 

def test(temp):
    import os
    import sys

    f = open('/home/vishal/workspace/abc.txt', 'w')
    f.write(temp)
    f.close()

import logging
try:
    import helper
except Exception, e:
    test(str(e))

import services
from globals import Globals

_log = logging.getLogger(__name__)

logging_list = []
logging_level = logging.INFO
format = '%(asctime)-15s %(levelname)-6s %(thread)d - %(module)-s[%(lineno)-d]: %(message)s'
exe_path = helper.Utils.get_exe_path()
logging.basicConfig(level = logging_level, format = format)

try:
    lf = logging.FileHandler(helper.Utils.get_safe_path(exe_path + 'var/log/sealion.log'))
except Exception, e:
    _log.error('Failed to open log file; ' + str(e))
    services.quit()
    
try:
    globals = Globals()
except RuntimeError, e:
    _log.error(str(e))
    services.quit()

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
    pass

formatter = logging.Formatter(format if logging_level == logging.DEBUG else format.replace('%(thread)d - ', ''))
logger = logging.getLogger()
lf.setFormatter(formatter)
logger.addHandler(lf)
logger.setLevel(logging_level)

if len(logging_list) != 1 or logging_list[0] != 'all':
    for handler in logging.root.handlers:
        handler.addFilter(LoggingList(*logging_list))

services.start()
