"""
Abstracts auth and reauth
Implements Connection
"""

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

_log = logging.getLogger(__name__)  #module level logging

class Connection(ThreadEx):    
    """
    Implements auth/reauth and socket-io instantiation
    """
    
    connect_lock = threading.RLock()  #lock to prevent multiple threads doing auth
    reconnect_lock = threading.RLock()  #lock to prevent multiple threads doing reauth
    
    def __init__(self):
        """
        Constructor
        """
        
        ThreadEx.__init__(self)  #initialize base class
        self.globals = globals.Globals()  #save the reference to globals for optimized access
        self.daemon = True  #set the daemon flag as we dont want this thread to block agent shutdown
    
    def exe(self):
        """
        Method that runs in the new thread.
        """
        
        if not Connection.connect_lock.acquire(blocking = False):  #try to acquire the lock, return on failure since anothor thread is doing auth
            return
        
        try:
            while 1:  #attempt until we dont get a bad request 
                if self.attempt(retry_interval = 10) != api.Status.BAD_REQUEST:
                    break
        finally:
            Connection.connect_lock.release()
    
    def attempt(self, retry_count = -1, retry_interval = 5):
        """
        Method to attempt authentication and socket-io instantiation
        
        Args:
            retry_count: number of times it should retry
            retry_interval: delay between successive retries
            
        Returns:
            status of auth request
        """
        
        rtc.create_session()  #create the socket-io
        status = api.Status.UNKNOWN
        api.session.auth_status = api.AuthStatus.AUTHENTICATING  #set api session authentication status to indicate progress

        while 1:
            status = api.session.authenticate(retry_count = retry_count, retry_interval = retry_interval)

            if status != api.Status.SUCCESS:
                break
            elif rtc.session.connect() != None:  #after a successful auth, connect socket-io session
                rtc.session.start()
                break

        return status
        
    def connect(self):        
        """
        Public method to authenticate the api session.
        The method tries auth for three times
        
        Returns:
            status of auth
        """
        
        if not Connection.connect_lock.acquire(blocking = False):  #try to acquire the lock, return on failure since anothor thread is doing auth
            return api.Status.UNKNOWN
        
        try:
            status = self.attempt(retry_count = 2)  #attempt to auth
        finally:
            Connection.connect_lock.release()
        
        #if api sesssion cannot connect to server and we have the activities available, we can run them offline
        if api.is_not_connected(status) and hasattr(self.globals.config.agent, 'activities') and hasattr(self.globals.config.agent, 'org'):
            self.start()
            status = api.Status.SUCCESS  #modify the status so that caller can continue
            
        return status
    
    def reconnect_helper(self):
        """
        Helper method to reauth if the reconnect was called from socket-io thread
        """
        
        self.reconnect()
    
    def reconnect(self):
        """
        Public method to reauth. Reauth will happen in a seperate thread.
        """
        
        #if the current thread is socket-io thread, we need to start a helper thread to avoid deadlock
        if isinstance(threading.current_thread(), rtc.RTC):
            reconnect_helper = ThreadEx(target = self.reconnect_helper, name = 'ReconnectHelper')  #helper thread
            reconnect_helper.daemon = True  #set the daemon flag as we dont want this thread to block agent shutdown
            reconnect_helper.start()
            return
        
        if not Connection.reconnect_lock.acquire(blocking = False):  #try to acquire the lock, return on failure since anothor thread is doing auth
            return
                
        try:
            if api.session.auth_status != api.AuthStatus.UNAUTHORIZED:
                return

            api.session.auth_status = api.AuthStatus.AUTHENTICATING  #set api session authentication status to indicate progress
            _log.info('Reauthenticating')

            if rtc.session:  #we need to terminat socket-io
                _log.info('Waiting for SocketIO to disconnect')
                helper.ThreadMonitor().register(callback = exit_status.AGENT_ERR_RESTART)  #register the thread for monitoring, as socket-io sometimes hangs
                rtc.session.join()
                helper.ThreadMonitor().unregister()  #unregister thread from monitoring

            self.start()  #do auth in another thread
        finally:
            Connection.reconnect_lock.release()

