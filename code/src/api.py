"""
Abstracts api to communicate with the server.
Implements Status, AuthStatus, API, is_not_connected, create_session and create_unauth_session
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import logging
import requests
import time
import json
import re
import connection
import universal
from constructs import *

_log = logging.getLogger(__name__)  #module level logging
session = None  #api session for agent
unauth_session = None  #unauthenticated session for api calls that doesnt rely on cookies

class Status(Namespace):
    """
    Various status codes for api response.
    """
    
    SUCCESS = 0  #request was successful
    NOT_CONNECTED = 1  #failed to reach server because of some client side issues
    NO_SERVICE = 2  #server is not available
    DATA_CONFLICT = 3  #posted data conflicted
    MISMATCH = 4  #not allowed at the moment
    BAD_REQUEST = 5  #bad api request.
    NOT_FOUND = 6  #agent not found in the organization
    UNAUTHORIZED = 7  #unauthorized session
    SESSION_CONFLICT = 8  #agent session conflict
    UNKNOWN = -1  #unknown reason
    
class AuthStatus(Namespace):
    """
    Authentication state for api session.
    """
    
    UNAUTHORIZED = 0  #unauthorized session
    AUTHENTICATING = 1  #session authentication in progress
    AUTHENTICATED = 2  #session authenticated

class API(requests.Session):   
    """
    Implements server apis.
    """
    
    def __init__(self, *args, **kwargs):
        """
        Constructor
        """
        
        requests.Session.__init__(self, *args, **kwargs)  #initialize the base class
        self.univ = universal.Universal()  #save the reference to Universal for optimized access
        self.stop_status = Status.SUCCESS  #reason for stopping
        self.authenticate_status = AuthStatus.UNAUTHORIZED  #authentication status
        self.auth_lock = threading.RLock()  #lock for authentication status
        self.is_conn_err = False  #last api call returned error
            
    @staticmethod
    def is_success(response):
        """
        Static method to check whether the request was successfull.
        
        Args:
            response: response object for request. This can be None.
            
        Returns:
            True if successfull else false
        """
        
        status_code = response.status_code if response else 500
        return True if (status_code == 304 or (status_code >= 200 and status_code < 300)) else False
    
    @staticmethod
    def print_error(message, response):
        """
        Static method to log error.
        
        Args:
            message: a message to be logged
            response: response instance for which the error to be logged.
        """
        
        temp = 'Client side failure'  #default case if response is None
        
        if response != None:
            try:
                #try to get response error code and message
                response_json = response.json()
                temp = 'Error %d; %s' % (response_json['code'], response_json['message'])
            except:
                temp = 'Error %d' % response.status_code  #if content is not available, log status code
        
        temp = '%s; %s' % (message, temp) if len(message) else temp
        _log.error(temp)
    
    def set_events(self, stop_event = None, post_event = None):
        """
        Method to set stop even and post event
        
        Args:
            stop_event: set/reset stop event if True/False
            post_event: set/reset stop event if True/False
        """
                
        if stop_event == True and self.univ.stop_event.is_set() == False:  #set stop event if it is not set
            _log.debug('Setting stop event')
            self.univ.stop_event.set()
        elif stop_event == False and self.univ.stop_event.is_set() == True:  #reset stop event if it is not reset
            _log.debug('Resetting stop event')
            self.univ.stop_event.clear()
        
        if post_event == True and self.univ.post_event.is_set() == False:  #set post event if it is not set
            _log.debug('Setting post event')
            self.univ.post_event.set()
        #reset post event if it is not set and stop event is reset. 
        #if stop event is set, it means agent want to shutdown, and resetting post event can delay shutdown if any threads waiting for it.
        elif post_event == False and self.univ.post_event.is_set() == True and self.univ.stop_event.is_set() == False:
            _log.debug('Resetting post event')
            self.univ.post_event.clear()
    
    def exec_method(self, method, url, **kwargs):
        """
        Public method to call the supplied http method with the arguments given.
        
        Args:
            method: http method to call.
            url: url for the request
            
        Returns:
            Tupple of (response object, any exception) if kwargs['options'] has is_return_exception set to True, else it returns response object
        """
        
        method = getattr(self, method.lower())  #get the method to be executed
        
        if kwargs.get('options'):  #get options for method call
            options = kwargs['options']
            del kwargs['options']
        else:
            options = {}
            
        retry_count = options.get('retry_count', -1)  #retry count, -1 indicates infinite retry
        retry_interval = options.get('retry_interval', 5)  #retry interval
        is_ignore_stop_event = options.get('is_ignore_stop_event', False)  #whether to consider stop event
        is_return_exception = options.get('is_return_exception', False) #whether to return any exception raised 
        response, i, exception = None, 0, None
        
        #convert data to string if it is not
        if type(kwargs.get('data')) is dict and kwargs.get('headers') == None:
            kwargs['headers'] = {'Content-type': 'application/json', 'Accept': 'text/plain'}
            kwargs['data'] = json.dumps(kwargs['data'])
        
        is_check_auth = True if re.match('^.+/agents/1(/.*)?\s*$', url) else False  #is this call requires session authentication
        
        while retry_count == -1 or i <= retry_count:  #retry as many time as requested
            if i > 0:  #wait for stop event, before retrying
                self.univ.stop_event.wait(retry_interval)
                
            if is_ignore_stop_event == False and self.univ.stop_event.is_set():  #do we need to stop
                break
            
            try:     
                if is_check_auth and not self.is_authenticated():
                    raise Exception('session not authenticated')
                
                response = method(url, timeout = 10, **kwargs)  #actuall request
            except Exception as e:
                _log.error('Failed URL request; %s' % unicode(e))
                exception = e
                
            #if the previous request failed due to a connection error, we just log that the connection is now available
            if response != None and response.status_code < 500:
                self.is_conn_err == True and _log.info('Network connection established')
                self.is_conn_err = False
                break
                
            i += 0 if (retry_count == -1 and i > 0) else 1
            
        if response == None and self.is_authenticated():  #set the connection error flag
            self.is_conn_err = True
        
        return response if is_return_exception == False else (response, exception)
    
    def ping(self, is_ping_server = False):
        """
        Method to ping, unblocking any post event wait
        
        Args:
            is_ping_server: whether to actually ping the api server, or just unblock post event wait
            
        Returns:
            response object if is_ping_server, else None
        """
        
        response = None
        
        if is_ping_server == False:  #only unblock post event
            self.set_events(post_event = True)
        else:
            response = self.exec_method('get', self.univ.get_url(), options = {'retry_count': 0, 'is_return_exception': True})  #ping the server
            
            if response[0] != None and response[0].status_code < 500:  #we are able to reach the server
                _log.debug('Ping server successful')
                self.is_authenticated() and self.set_events(post_event = True)
            else:
                API.print_error('Failed to ping server', response[0])
            
        return response
    
    def register(self, **kwargs):
        """
        Public method to register agent.
        
        Returns:
            Status code for the request.
        """
        
        ret = Status.SUCCESS
        
        #get data and make the request
        data = self.univ.config.agent.get_dict(['orgToken', 'name', 'category', 'agentVersion', ('ref', 'tarball')])
        response = self.exec_method('post', self.univ.get_url('agents'), data = data, options = kwargs)    
        
        if API.is_success(response):
            _log.info('Registration successful')
            
            #update and save the config
            self.univ.config.agent.update(response.json())
            self.univ.config.agent.save()
        else:
            ret = self.error('Failed to register agent', response)
        
        return ret
    
    def unregister(self):
        """
        Public method to unregister agent.
        
        Returns:
            Status code for the request.
        """
        
        ret = Status.SUCCESS
        
        if hasattr(self.univ.config.agent, '_id') == False:  #if this agent was not registered
            return ret
        
        #make the request
        response = self.exec_method('delete', 
            self.univ.get_url('orgs/%s/servers/%s' % (self.univ.config.agent.orgToken, self.univ.config.agent._id)), options = {'retry_count': 2})
        
        if API.is_success(response) == False:
            ret = self.error('Failed to unregister agent', response)
            
        return ret
    
    def authenticate(self, **kwargs):
        """
        Public method to authenticate agent.
        
        Returns:
            Status code for the request.
        """
        
        ret = Status.SUCCESS
        
        #get data and make the request
        data = self.univ.config.agent.get_dict(['orgToken', 'agentVersion'])
        data['timestamp'] = int(time.time() * 1000)
        data['platform'] = self.univ.details
        response = self.exec_method('post', self.univ.get_url('agents/' + self.univ.config.agent._id + '/sessions'), data = data, options = kwargs)    
        
        if API.is_success(response):
            _log.info('Authentication successful')
            
            #update and save the config
            self.univ.config.agent.update(response.json())
            self.univ.config.agent.save()
            
            self.auth_status(AuthStatus.AUTHENTICATED)  #set auth sataus
            self.set_events(post_event = True)  #set the post event so that data can posted
        else:
            ret = self.error('Authentication failed', response)
        
        return ret
            
    def get_config(self):
        """
        Public method to get agent config.
        
        Returns:
            Status code for the request.
        """
        
        ret = Status.SUCCESS
        response = self.exec_method('get', self.univ.get_url('agents/1'), options = {'retry_count': 0})  #make the request
        
        if API.is_success(response):
            _log.info('Config updation successful')
            
            #update and save the config
            self.univ.config.agent.update(response.json())
            self.univ.config.agent.save()
            
            self.set_events(post_event = True)  #set the post event so that data can posted
        else:
            ret = self.error('Config updation failed', response)
            
        return ret
            
    def post_data(self, activity_id, data):
        """
        Public method to post the activity data.
        
        Args:
            activity_id: activity id of the data
            data: data to be posted
        
        Returns:
            Status code for the request.
        """
        
        ret = Status.SUCCESS
        
        #make the request
        response = self.exec_method('post', self.univ.get_url('agents/1/data/activities/' + activity_id), data = data, options = {'retry_count': 0})
        
        if API.is_success(response):
            _log.debug('Sent activity (%s @ %d)' % (activity_id, data['timestamp']))
            self.set_events(post_event = True)  #set the post event so that data can posted
        else:
            ret = self.error('Failed to send activity (%s @ %d)' % (activity_id, data['timestamp']), response)
            
        return ret
    
    def logout(self):
        """
        Public method to logout api session.
        
        Returns:
            Status code for the request.
        """
        
        ret = Status.SUCCESS
        
        #make request
        response = self.exec_method('delete', self.univ.get_url('agents/1/sessions/1'), options = {'retry_count': 0, 'is_ignore_stop_event': True})
        
        if API.is_success(response):
            _log.info('Logout successful')
            self.auth_status(AuthStatus.UNAUTHORIZED)  #reset auth status
        else:
            ret = self.error('Logout failed', response, True)

        return ret
    
    def get_agent_version(self):
        """
        Public method to get agent version, after this call api session will be invalid.
        
        Returns:
            Status code for the request.
        """
        
        #get the data, url and make the request
        data = self.univ.config.agent.get_dict([('orgToken', ''), ('_id', ''), ('agentVersion', '')])
        url = self.univ.get_url('orgs/%s/agents/%s/agentVersion' % (data['orgToken'], data['_id']))
        response = self.exec_method('get', url, params = {'agentVersion': data['agentVersion']}, options = {'retry_count': 0})
        
        if API.is_success(response):
            ret = response.json()
            _log.debug('Available agent version %s' % ret['agentVersion'])
        else:
            ret = self.error('Failed to get agent version', response, True)
            ret == Status.MISMATCH and self.stop()
        
        return ret
    
    def send_crash_report(self, data, **kwargs):
        """
        Public method to send the crash report, after this call api session will be invalid.
        
        Args:
            data: crash report to send.
        
        Returns:
            Status code for the request.
        """
        
        ret = Status.SUCCESS
        data = data.copy()  #make a deep copy of the report so that we can remove extra attribute from it
        orgToken, agentId = data['orgToken'], data['_id']
        del data['orgToken'], data['_id']
        
        #make request
        response = self.exec_method('post', self.univ.get_url('orgs/%s/agents/%s/crashreport' % (orgToken, agentId)), 
            data = data, options = {'retry_count': 0})
        
        if API.is_success(response):
            _log.info('Sent dump @ %d' % data['timestamp'])
        else:
            ret = self.error('Failed to send dump', response, True)
        
        return ret
    
    def stop(self, stop_status = None):
        """
        Public method to stop api, there by stopping the agent.
        
        Args:
            stop_status: reson for stopping if any.
        """
        
        self.set_events(True, True)  #set both events
        
        if stop_status != None:
            self.stop_status = stop_status
    
    def error(self, message, response, is_ignore_status = False):
        """
        Method to log error, and perform action based on the response status.
        
        Args:
            message: message to be logged.
            response: response object for which the error to be logged.
            is_ignore_status: whether to perform action based on the response status.
            
        Returns:
            Error code.
        """
        
        API.print_error(message, response)  #log the error  
        
        if response == None:  #client error for the request. reset the post event 
            is_ignore_status == False and self.univ.stop_event.is_set() == False and self.set_events(post_event = False)
            return Status.NOT_CONNECTED
        
        status, ret, post_event, exec_func, args = response.status_code, Status.UNKNOWN, True, None, ()
        
        try:
            code = response.json()['code']  #try to extract the error code
        except:
            code = 0
            
        if status >= 500:  #cannot reach server
            post_event = False
            ret = Status.NO_SERVICE
        elif status == 400:  #bad request
            ret = Status.BAD_REQUEST
        elif status == 401:
            if code == 200004:  #data not allowed to post
                ret = Status.MISMATCH
            else:
                if code == 200001 and self.stop_status == Status.SUCCESS:  #unauthorized session, reconnect
                    if self.auth_status(AuthStatus.UNAUTHORIZED):
                        post_event = False
                        exec_func = connection.Connection().reconnect  #reconnect
                else:
                    post_event = None
                    exec_func = self.stop
                    
                ret = Status.UNAUTHORIZED
        elif status == 404:  #agent not found
            post_event = None
            exec_func = self.stop
            args = (Status.NOT_FOUND,)
            ret = Status.NOT_FOUND
        elif status == 409:  #conflict
            if code == 204011:
                ret = Status.DATA_CONFLICT  #duplicate data
            elif code == 204012:  #another agent session running for the same agent id
                post_event = None  #just ignore this, as cookie handling is not thread safe and can cause this
                
        if is_ignore_status == False:  #perform any actions
            self.set_events(post_event = post_event)
            exec_func and exec_func(*args)
            
        return ret
    
    def is_authenticated(self):
        """
        Public function to check whether the session is authenticated.
        
        Returns:
            True if authenticated, else False
        """
        
        return True if self.auth_status() == AuthStatus.AUTHENTICATED else False
    
    def auth_status(self, status = None):
        """
        Public function to get or set auth status
        
        Args:
            status: auth status to be set, supply None to retreive status
        
        Returns:
            Auth status if status is None
            True if status changed else False
        """
        
        self.auth_lock.acquire()  #this has to be atomic as multiple threads reads/wirtes
        
        try:
            if status == None:  #return current status
                return self.authenticate_status
            else:
                if self.authenticate_status == status:  #the status already set
                    return False
                elif self.authenticate_status == AuthStatus.AUTHENTICATING and status == AuthStatus.UNAUTHORIZED:  #we cannot change status to unauthorized from authetnicating
                    return False
                else:
                    self.authenticate_status = status  #set the new status
                    return True
        finally:
            self.auth_lock.release()
    
def is_not_connected(status):
    """
    Function to check whether status indicates failed connection.
    
    Args:
        status: status to be checked.
    
    Returns:
        True if status identified as not connected, else False
    """
    
    if status == Status.NOT_CONNECTED or status == Status.NO_SERVICE or status == Status.UNKNOWN:
        return True

    return False
    
def create_session():
    """
    Function to create the api session for agent.
    
    Returns:
        api session.
    """
    
    global session
    session = API()
    return session

def create_unauth_session():
    """
    Function to create the unauth api session for agent. 
    Crash dump sending and agent version retreival should be performed using this session.
    
    Returns:
        Unauth api session.
    """
    
    global unauth_session
    unauth_session = API()
    return unauth_session
