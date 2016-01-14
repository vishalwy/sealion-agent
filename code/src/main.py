"""
In a development environment this script is used as the main script.
It sets up logging, Universal and api sessions.
When used as main script this starts the agent execution.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import sys
import logging
import logging.handlers
import gc
import re

#agent base directory
exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]

import helper
import controller
import api
import exit_status
from universal import Universal
from constructs import *

_log = logging.getLogger(__name__)  #module level logging
gc.set_threshold(50, 5, 5)  #set gc threshold
logging_level = logging.INFO  #default logging level

#setup logging for StreamHandler
#in StreamHandler we display only messages till everything initializes. This is done not polute the terminal when running as service
logging.basicConfig(level = logging_level, format = '%(message)s') 

formatter = logging.Formatter('%(asctime)-15s %(levelname)-7s %(thread)d - %(module)-s[%(lineno)-d]: %(message)s')  #formatter instance for logging
logger = logging.getLogger()  #get the root logger

try:
    #create rotating file logger and add to root logger
    #this can raise exception if the file cannot be created
    lf = logging.handlers.RotatingFileHandler(helper.Utils.get_safe_path(exe_path + '/var/log/sealion.log'), maxBytes = 1024 * 1024 * 10, backupCount = 5)
    lf.setFormatter(formatter)
    logger.addHandler(lf)
except Exception as e:
    sys.stderr.write('Failed to open the log file; %s\n' % unicode(e))
    sys.exit(exit_status.AGENT_ERR_FAILED_OPEN_LOG)
    
try:
    #set the home folder for the process; do it before parsing config files so that user can override it in config file
    os.environ['HOME'] = exe_path or '/' 

    #initialize Universal and create api sessions
    #this can raise exception if universal is failed to find/create config files
    univ = Universal()
    api.create_session()
    api.create_unauth_session()
except Exception as e:
    _log.error(unicode(e))
    sys.exit(exit_status.AGENT_ERR_FAILED_INITIALIZE)
    
class LoggingList(logging.Filter):
    """
    Class to filter module wise logging 
    """
    
    def __init__(self, *logging_filters):
        """
        Constructor
        """
        
        self.log_filters = [re.compile('.*%s.*' % log_filter) for log_filter in logging_filters]  #create a filter list

    def filter(self, record):
        """
        Method is called every time something is logged
        
        Args:
            record: record to be logged
            
        Returns:
            True if filter is successful else False
        """
        
        return any(log_filter.match(record.pathname) for log_filter in self.log_filters)

logging_filters = univ.config.sealion.get(['logging', 'modules'], ['/(src|opt)/.+\\.py'])  #read any logging list defined in the config
temp = univ.config.sealion.get(['logging', 'level'])  #read logging level from config

#set the level based on the string
if temp == 'error':
    logging_level = logging.ERROR
elif temp == 'debug':
    logging_level = logging.DEBUG
elif temp == 'none':  #if logging need to be done set the level to the highest and filterout all the logs
    logging_level = logging.CRITICAL
    logging_filters = []
    
#setup log filtering       
for handler in logger.handlers:  
    handler.addFilter(LoggingList(*logging_filters))
        
#if the agent is already registerd, thare will be _id attribute
if not univ.config.agent.get(['config', '_id']):  
    if api.session.register(retry_count = 2, retry_interval = 10) != api.Status.SUCCESS:
        sys.exit(exit_status.AGENT_ERR_FAILED_REGISTER)
        
logger.setLevel(logging_level)  #set the logging level

#set the formatter for all the logging handlers, including StreamHandler
for handler in logger.handlers:
    handler.setFormatter(formatter)
    
def stop_stream_logging():
    """
    Function to disable logging to stdout/stderr
    """
    
    #loop through handlers and remove stream handlers
    for stream_handler in [handler for handler in logger.handlers if type(handler) is logging.StreamHandler]:
        logger.removeHandler(stream_handler)
               
def run(is_update_only_mode = False):
    """
    Function that starts the agent execution.
    
    Args:
        is_update_only_mode: whether to run the agent in update only mode
    """

    univ.is_update_only_mode = is_update_only_mode
    _log.info('Agent starting up')
    _log.info('Using python binary at %s' % sys.executable)
    _log.info('Python version : %s' % univ.details['pythonVersion'])
    _log.info('Agent user     : %s' % univ.details['user'])  
    _log.info('Agent version  : %s' % univ.config.agent.agentVersion)  
    controller.run()  #call the run method controller module to start the controller
    _log.info('Agent shutting down with status code 0')
    _log.debug('Took %f seconds to shutdown' % (univ.get_stoppage_time()))
    _log.info('Ran for %s hours' %  univ.get_run_time_str())
    helper.notify_terminate()  #send terminate event so that modules listening on the event will get a chance to cleanup
    sys.exit(exit_status.AGENT_ERR_SUCCESS)

