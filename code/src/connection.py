"""
Abstracts auth and reauth
Implements Connection
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import logging
import globals
import api
import rtc
from constructs import *

_log = logging.getLogger(__name__)  #module level logging

class Connection(ThreadEx):    
    """
    Implements auth/reauth and socket-io instantiation
    """
    
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
        
        while 1:  #attempt until we dont get a bad request 
            if self.attempt(retry_interval = 10) != api.Status.BAD_REQUEST:
                break
    
    def attempt(self, retry_count = -1, retry_interval = 5):
        """
        Method to attempt authentication and socket-io instantiation
        
        Args:
            retry_count: number of times it should retry
            retry_interval: delay between successive retries
            
        Returns:
            status of auth request
        """
        
        api.session.auth_status(api.AuthStatus.AUTHENTICATING)  #set auth status
        status = api.session.authenticate(retry_count = retry_count, retry_interval = retry_interval)  #authenticate

        if status == api.Status.SUCCESS and rtc.session == None:  #create socket-io session
            rtc.create_session().start()
            
        return status
        
    def connect(self):        
        """
        Public method to authenticate the api session.
        The method tries auth for three times before giving it to the background thread in case of connection issues.
        
        Returns:
            status of auth
        """
        
        #if the session is not authorized or another thread is performing auth, then we return
        if api.session.auth_status() != api.AuthStatus.UNAUTHORIZED or not api.session.auth_status(api.AuthStatus.AUTHENTICATING):
            return api.Status.UNKNOWN
        
        status = self.attempt(retry_count = 2)  #attempt to auth
        
        #if api sesssion cannot connect to server and we have the activities available, we can run them offline
        if api.is_not_connected(status) and hasattr(self.globals.config.agent, 'activities') and hasattr(self.globals.config.agent, 'org'):
            self.start()
            status = api.Status.SUCCESS  #modify the status so that caller can continue
            
        return status
    
    def reconnect(self):
        """
        Public method to reauth api session. Reauth will happen in a seperate thread.
        """
        
        #if the session is not authorized or another thread is performing auth, then we simply return
        if api.session.auth_status() != api.AuthStatus.UNAUTHORIZED or not api.session.auth_status(api.AuthStatus.AUTHENTICATING):
            return
        
        self.start()  #do auth in another thread


