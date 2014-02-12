import logging
from constructs import *

_log = logging.getLogger(__name__)

class Interface(ExceptionThread):
    globals = None
    
    def __init__(self, globals = None):
        Interface.globals = Interface.globals or globals
        ExceptionThread.__init__(self)
    
    def exe(self):
        _log.debug('Starting up connection')
        self.attempt(retry_interval = 20)
        _log.debug('Shutting down connection')
    
    def attempt(self, max_try = -1, retry_interval = 5):
        status = Interface.globals.api.authenticate(max_try, retry_interval)
        
        if status == Interface.globals.APIStatus.SUCCESS and Interface.globals.is_update_only_mode == False: 
            Interface.globals.rtc.connect().start()
            
        return status            
        
    def connect(self):        
        status = self.attempt(2)
        
        if Interface.globals.api.is_not_connected(status):
            if Interface.globals.is_update_only_mode == True:
                self.start()
                status = Interface.globals.APIStatus.SUCCESS
            elif hasattr(Interface.globals.config.agent, 'activities') and hasattr(Interface.globals.config.agent, 'org'):
                _log.info('Running commands in offline mode')
                self.start()
                status = Interface.globals.APIStatus.SUCCESS
            
        return status
    
    def reconnect(self):
        if Interface.globals.api.is_authenticated == False:
            return
        
        _log.info('Reauthenticating')
        Interface.globals.rtc.stop()
        _log.info('Waiting for socket-io to disconnect')
        Interface.globals.rtc.join()
        Interface.globals.reset_rtc_interface()
        self.start()
