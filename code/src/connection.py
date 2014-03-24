__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import logging
import threading
import time
import globals
import api
import rtc
import exit_status
import helper
from constructs import *

_log = logging.getLogger(__name__)

class Connection(ThreadEx):    
    def __init__(self):
        ThreadEx.__init__(self)
        self.globals = globals.Globals()
        self.api = api.API()
    
    def exe(self):
        while 1:
            if self.attempt(retry_interval = 10) != api.status.BAD_REQUEST:
                break
    
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
    
    def reconnect_helper(self):
        self.reconnect()
    
    def reconnect(self):
        if self.api.is_authenticated == False:
            return
        
        if isinstance(threading.current_thread(), rtc.RTC):
            ThreadEx(target = self.reconnect_helper, name = 'ReconnectHelper').start()
            return
        
        self.api.is_authenticated = False
        _log.info('Reauthenticating')
        rtc_thread = Connection.stop_rtc()
        
        if rtc_thread:
            _log.info('Waiting for SocketIO to disconnect')
            helper.Terminator().start(exit_status.AGENT_ERR_TERMINATE, rtc_thread.join)
            helper.Terminator().stop()
                
        self.start()
        
    @staticmethod
    def stop_rtc():
        for thread in threading.enumerate():
            if isinstance(thread, rtc.RTC):
                thread.stop()
                return thread
        
        return None

