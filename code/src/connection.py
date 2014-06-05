__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import logging
import threading
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
        self.daemon = True
    
    def exe(self):
        while 1:
            if self.attempt(retry_interval = 10) != api.Status.BAD_REQUEST:
                break
    
    def attempt(self, retry_count = -1, retry_interval = 5):
        rtc.create_session()
        status = api.Status.UNKNOWN
        api.session.auth_status = api.AuthStatus.AUTHENTICATING
        
        while 1:
            status = api.session.authenticate(retry_count = retry_count, retry_interval = retry_interval)
        
            if status != api.Status.SUCCESS:
                break
            elif rtc.session.connect() != None:
                rtc.session.start()
                break
            
        return status
        
    def connect(self):        
        status = self.attempt(retry_count = 2)
        
        if api.is_not_connected(status) and hasattr(self.globals.config.agent, 'activities') and hasattr(self.globals.config.agent, 'org'):
            self.start()
            status = api.Status.SUCCESS
            
        return status
    
    def reconnect_helper(self):
        self.reconnect()
    
    def reconnect(self):
        curr_thread = threading.current_thread()
        helper_thread_name = 'ReconnectHelper'
        
        if api.session.auth_status != api.AuthStatus.UNAUTHORIZED and curr_thread.name != helper_thread_name:
            return
        
        api.session.auth_status = api.AuthStatus.AUTHENTICATING
        
        if isinstance(threading.current_thread(), rtc.RTC):
            reconnect_helper = ThreadEx(target = self.reconnect_helper, name = helper_thread_name)
            reconnect_helper.daemon = True
            reconnect_helper.start()
            return
        
        _log.info('Reauthenticating')
        
        if rtc.session:
            _log.info('Waiting for SocketIO to disconnect')
            helper.ThreadMonitor().register(callback = exit_status.AGENT_ERR_RESTART)
            rtc.session.join()
            helper.ThreadMonitor().unregister()
                
        self.start()

