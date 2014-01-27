#!/usr/bin/python
import sys
sys.path.append('lib')
sys.path.append('src')
sys.path.append('lib/websocket_client') 
import logging
import services
from globals import Globals

_log = logging.getLogger(__name__)
logging_list = []
logging_level = logging.INFO
logging.basicConfig(level = logging_level, format = '%(asctime)-15s %(levelname)-8s %(module)-s[%(lineno)-d]: %(message)s')

try:
    globals = Globals()
except RuntimeError, e:
    _log.error(e)
    services.quit()

class LoggingList(logging.Filter):
    def __init__(self, *logs):
        self.logs = [logging.Filter(log) for log in logs]

    def filter(self, record):
        return any(log.filter(record) for log in self.logs)

try:
    temp = globals.config.sealion.logging['level'].strip()
    
    if temp == 'error':
        logging_level = logging.ERROR
    elif temp == 'debug':
        logging_level = logging.DEBUG
except:
    pass

try:
    logging_list = globals.config.sealion.logging['modules']
except:
    pass

logging.getLogger().setLevel(logging_level)

for handler in logging.root.handlers:
    handler.addFilter(LoggingList(*logging_list))

services.start()
