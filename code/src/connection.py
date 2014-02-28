import logging
from constructs import *
from globals import Globals
from api import API
from rtc import RTC

_log = logging.getLogger(__name__)

class Interface(ThreadEx):    
    def __init__(self):
        ThreadEx.__init__(self)
        self.globals = Globals()
        self.api = API()
    
    def exe(self):
        _log.debug('Starting up connection')
        self.attempt(retry_interval = 10)
        _log.debug('Shutting down connection')
    
    def attempt(self, retry_count = -1, retry_interval = 5):
        status = self.api.authenticate(retry_count = retry_count, retry_interval = retry_interval)
        status == self.api.status.SUCCESS and RTC().connect().start()
        return status            
        
    def connect(self):        
        status = self.attempt(2)
        
        if self.api.is_not_connected(status) and hasattr(self.globals.config.agent, 'activities') and hasattr(self.globals.config.agent, 'org'):
            _log.info('Running commands in offline mode')
            self.start()
            status = self.api.status.SUCCESS
            
        return status
    
    def reconnect(self):
        if self.api.is_authenticated == False:
            return
        
        self.api.is_authenticated = False
        _log.info('Reauthenticating')
        threads = threading.enumerate()
        
        for thread in threads:
            if isinstance(thread, RTC):
                thread.stop()
                _log.info('Waiting for socket-io to disconnect')
                thread.join()
                break
                
        self.start()
        
Connection = Interface
