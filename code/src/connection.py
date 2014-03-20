__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__license__ = 'GPL'
__email__ = 'support@sealion.com'

import logging
import threading
import time
import globals
import api
import rtc
from constructs import *

_log = logging.getLogger(__name__)

class Connection(ThreadEx):    
    def __init__(self):
        ThreadEx.__init__(self)
        self.globals = globals.Globals()
        self.api = api.API()
    
    def exe(self):
        self.attempt(retry_interval = 10)
    
    def attempt(self, retry_count = -1, retry_interval = 5):
        status = self.api.authenticate(retry_count = retry_count, retry_interval = retry_interval)
        status == self.api.status.SUCCESS and rtc.RTC().connect().start()
        return status            
        
    def connect(self):        
        status = self.attempt(2)
        
        if self.api.is_not_connected(status) and hasattr(self.globals.config.agent, 'activities') and hasattr(self.globals.config.agent, 'org'):
            _log.info('Running in offline mode')
            self.start()
            status = self.api.status.SUCCESS
            
        return status
    
    def reconnect(self):
        if self.api.is_authenticated == False or isinstance(threading.current_thread(), rtc.RTC):
            return
        
        self.api.is_authenticated = False
        _log.info('Reauthenticating')
        rtc_thread = Connection.stop_rtc()
        
        if rtc_thread:
            _log.info('Waiting for SocketIO to disconnect')
            count = 0
            
            while count < 4:
                if rtc_thread.is_alive() == False:
                    break
                    
                time.sleep(5)
                count += 1
            
            if count > 3:
                _log.info('SocketIO not responding. Self terminating service.')
                self.globals.stop_status = 1
                self.api.stop()
                return
                
        self.start()
        
    @staticmethod
    def stop_rtc():
        for thread in threading.enumerate():
            if isinstance(thread, rtc.RTC):
                thread.stop()
                return thread
        
        return None

