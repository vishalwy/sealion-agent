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
        status == Interface.globals.APIStatus.SUCCESS and Interface.globals.rtc.connect().start()
        return status            
        
    def connect(self):        
        status = self.attempt(2)
        
        if Interface.globals.api.is_not_connected(status) and hasattr(Interface.globals.config.agent, 'activities') and hasattr(Interface.globals.config.agent, 'org'):
            _log.info('Running commands in offline mode')
            self.start()
            status = Interface.globals.APIStatus.SUCCESS
            
        return status
    
    def reconnect(self):
        if Interface.globals.api.is_authenticated == False:
            return
        
        Interface.globals.api.is_authenticated = False
        _log.info('Reauthenticating')
        Interface.globals.rtc.stop()
        _log.info('Waiting for socket-io to disconnect')
        Interface.globals.rtc.join()
        Interface.globals.reset_rtc_interface()
        self.start()
