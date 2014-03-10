import logging
import threading
import globals
import api
import rtc
from constructs import *

_log = logging.getLogger(__name__)

class Connection(ThreadEx):    
    def __init__(self):
        ThreadEx.__init__(self)
        self.globals = globals.Interface()
        self.api = api.Interface()
    
    def exe(self):
        self.attempt(retry_interval = 10)
    
    def attempt(self, retry_count = -1, retry_interval = 5):
        status = self.api.authenticate(retry_count = retry_count, retry_interval = retry_interval)
        status == self.api.status.SUCCESS and rtc.Interface().connect().start()
        return status            
        
    def connect(self):        
        status = self.attempt(2)
        
        if self.api.is_not_connected(status) and hasattr(self.globals.config.agent, 'activities') and hasattr(self.globals.config.agent, 'org'):
            _log.info('Running commands in offline mode')
            self.start()
            status = self.api.status.SUCCESS
            
        return status
    
    def reconnect(self):
        if self.api.is_authenticated == False or isinstance(threading.current_thread(), rtc.Interface):
            return
        
        self.api.is_authenticated = False
        _log.info('Reauthenticating')
        rtc_thread = Connection.stop_rtc()
        
        if rtc_thread:
            _log.info('Waiting for SocketIO to disconnect')
            rtc_thread.join()
                
        self.start()
        
    @staticmethod
    def stop_rtc():
        for thread in threading.enumerate():
            if isinstance(thread, rtc.Interface):
                thread.stop()
                return thread
        
        return None
        
Interface = Connection
